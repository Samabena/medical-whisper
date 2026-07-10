"""Relais full-duplex client ↔ agent vocal (LIVE-7.2).

Deux boucles concurrentes :
- `from_client` : audio micro → agent ; contrôle (`end_turn`/`stop`/`user_text`).
- `from_agent`  : audio agent → client ; transcript → client + extracteur → `form_state`.

Un tour utilisateur (qu'il vienne de la voix transcrite OU d'un message texte de test)
est traité par `process_user` : extraction, émission `form_state`, détection de
complétion. La première boucle qui se termine arrête proprement l'autre.
"""

from __future__ import annotations

import array
import asyncio
import logging
import math
import sys
import time

from app.application.live.completion import form_state_to_dict, is_complete
from app.application.live.connection import AudioFrame, ClientConnection, Closed, Control
from app.application.ports.extractor import FormExtractorPort
from app.application.ports.metrics import Metrics
from app.application.ports.repositories import SessionRepo
from app.application.ports.result_store import SessionResultStore
from app.application.ports.speech_agent import (
    AgentTurnEnd,
    AudioChunk,
    Backchannel,
    SpeechEndpoint,
    SpeechError,
    SpeechSession,
    TextDrivenSession,
    Transcript,
)
from app.domain.entities import FormDefinition, FormState, LiveSession
from app.domain.value_objects import SessionStatus

logger = logging.getLogger(__name__)


def _rms_pcm16(frame: bytes) -> float:
    """Énergie (RMS) d'une trame PCM signée 16 bits little-endian.

    Sert de VAD léger pour le barge-in : les trames de silence ont un RMS ~0, la parole
    un RMS élevé. 0.0 si trame vide/incomplète. Stdlib uniquement (pas de numpy backend)."""
    n = len(frame) - (len(frame) % 2)
    if n <= 0:
        return 0.0
    echantillons = array.array("h")
    echantillons.frombytes(frame[:n])
    if sys.byteorder == "big":  # l'entrée (navigateur) est little-endian
        echantillons.byteswap()
    somme = 0
    for s in echantillons:
        somme += s * s
    return math.sqrt(somme / len(echantillons))


class RunLiveDialogue:
    def __init__(
        self,
        extractor: FormExtractorPort,
        results: SessionResultStore,
        sessions: SessionRepo,
        max_user_turns: int = 12,
        metrics: Metrics | None = None,
        *,
        speculative_trigger: bool = False,
        barge_in: bool = False,
        barge_in_rms: float = 900.0,
        barge_in_min_frames: int = 3,
        backchannel: bool = False,
        backchannel_text: str = "D'accord…",
    ) -> None:
        self._extractor = extractor
        self._results = results
        self._sessions = sessions
        self._max_turns = max_user_turns
        self._metrics = metrics
        # Leviers de latence (LIVE-7.4), désactivés par défaut — câblés depuis la config.
        self._speculative = speculative_trigger
        self._barge_in = barge_in
        self._barge_in_rms = barge_in_rms
        self._barge_in_min_frames = barge_in_min_frames
        self._backchannel_on = backchannel
        self._backchannel_text = backchannel_text

    def _metric_incr(self, name: str) -> None:
        if self._metrics is not None:
            self._metrics.incr(name)

    def _metric_observe(self, name: str, value_ms: float) -> None:
        if self._metrics is not None:
            self._metrics.observe(name, value_ms)

    async def execute(
        self,
        conn: ClientConnection,
        agent: SpeechSession,
        form: FormDefinition,
        session: LiveSession,
    ) -> None:
        state = FormState()
        turns = {"n": 0}
        flags = {"completed": False}
        done = asyncio.Event()
        # Dernier partiel utilisateur « stable » (pour le déclenchement spéculatif).
        last_partial = {"text": ""}
        # Suivi de la prise de parole de l'agent (pour le barge-in) et timing endpoint.
        speaking = {"on": False, "interrupted": False}
        # Compteur de trames micro « voisées » consécutives (VAD du barge-in).
        voiced = {"n": 0}
        timing: dict[str, float | None] = {"endpoint": None}

        async def process_user(text: str, *, count_turn: bool = True) -> None:
            """Extrait, émet `form_state`, teste la complétion.

            `count_turn=False` pour une passe **spéculative** (sur partiel stable) : on
            n'incrémente pas le compteur de tours ; le final ré-extrait (fusion idempotente).
            """
            nonlocal state
            if done.is_set() or not text.strip():
                return
            if count_turn:
                turns["n"] += 1
                self._metric_incr("user_turns")
            debut = time.perf_counter()
            state = await self._extractor.update(text, form, state)
            await conn.send_json({"type": "form_state", "state": form_state_to_dict(state)})
            self._metric_observe("form_state_latency_ms", (time.perf_counter() - debut) * 1000)
            if is_complete(form, state):
                await self._finaliser(conn, state, session, "termine")
                flags["completed"] = True
                self._metric_incr("sessions_completed")
                done.set()
            elif count_turn and turns["n"] >= self._max_turns:
                await self._finaliser(conn, state, session, "incomplet")
                self._metric_incr("sessions_incomplete")
                done.set()

        async def on_endpoint() -> None:
            """Fin de parole détectée : backchannel immédiat + extraction spéculative."""
            timing["endpoint"] = time.perf_counter()
            if self._backchannel_on:
                await conn.send_json({"type": "backchannel", "text": self._backchannel_text})
                self._metric_observe("backchannel_latency_ms", 0.0)
                self._metric_incr("backchannel")
            if self._speculative and last_partial["text"].strip():
                await process_user(last_partial["text"], count_turn=False)

        async def from_client() -> None:
            while not done.is_set():
                msg = await conn.receive()
                if isinstance(msg, Closed):
                    done.set()
                    return
                if isinstance(msg, AudioFrame):
                    # Barge-in VAD (LIVE-7.4) : le micro streame en continu (silence compris),
                    # donc on ne coupe PAS sur une trame brute — sinon l'agent est interrompu
                    # dès son premier mot. On exige N trames « voisées » (énergie > seuil)
                    # CONSÉCUTIVES = vraie reprise de parole. L'annulation d'écho côté navigateur
                    # évite que la voix de l'agent captée par le micro déclenche un faux barge-in.
                    if self._barge_in and speaking["on"]:
                        if _rms_pcm16(msg.data) >= self._barge_in_rms:
                            voiced["n"] += 1
                        else:
                            voiced["n"] = 0
                        if voiced["n"] >= self._barge_in_min_frames:
                            voiced["n"] = 0
                            speaking["interrupted"] = True
                            speaking["on"] = False
                            self._metric_incr("barge_in")
                            logger.info("Barge-in : parole détectée (VAD) → coupure de l'agent")
                            await conn.send_json({"type": "interrupted"})
                    else:
                        voiced["n"] = 0
                    await agent.send_audio(msg.data)
                elif isinstance(msg, Control):
                    type_ = msg.payload.get("type")
                    if type_ == "end_turn":
                        await on_endpoint()
                        await agent.end_user_turn()
                    elif type_ == "user_text":  # tour de parole tapé (test/dev)
                        texte = msg.payload.get("text", "")
                        await conn.send_json(
                            {"type": "transcript", "speaker": "user", "text": texte, "final": True}
                        )
                        await process_user(texte)
                        if done.is_set():
                            return
                        # Agent conversationnel texte (dev) : il répond à la réplique tapée.
                        # Sa réponse arrive de façon asynchrone via la boucle `from_agent`.
                        if isinstance(agent, TextDrivenSession):
                            await agent.send_user_text(texte)
                    elif type_ == "stop":
                        done.set()
                        return

        async def from_agent() -> None:
            async for ev in agent.events():
                if done.is_set():
                    return
                if isinstance(ev, AudioChunk):
                    if speaking["interrupted"]:
                        continue  # audio agent supprimé jusqu'à la fin du tour (barge-in)
                    speaking["on"] = True
                    if timing["endpoint"] is not None:
                        self._metric_observe(
                            "endpoint_to_first_audio_ms",
                            (time.perf_counter() - timing["endpoint"]) * 1000,
                        )
                        timing["endpoint"] = None
                    await conn.send_audio(ev.data)
                elif isinstance(ev, Transcript):
                    await conn.send_json(
                        {"type": "transcript", "speaker": ev.speaker, "text": ev.text, "final": ev.is_final}
                    )
                    if ev.speaker == "user":
                        if ev.is_final and ev.text.strip():
                            last_partial["text"] = ""
                            await process_user(ev.text)
                            if done.is_set():
                                return
                        elif ev.stable and ev.text.strip():
                            last_partial["text"] = ev.text  # mémorisé pour le spéculatif
                elif isinstance(ev, SpeechEndpoint):
                    await on_endpoint()
                    if done.is_set():
                        return
                elif isinstance(ev, Backchannel):
                    await conn.send_json({"type": "backchannel", "text": ev.text})
                    if ev.audio:
                        await conn.send_audio(ev.audio)
                elif isinstance(ev, SpeechError):
                    await conn.send_json({"type": "error", "message": ev.message})
                    done.set()
                    return
                elif isinstance(ev, AgentTurnEnd):
                    speaking["on"] = False
                    speaking["interrupted"] = False

        t_in = asyncio.create_task(from_client())
        t_out = asyncio.create_task(from_agent())
        try:
            await asyncio.wait({t_in, t_out}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (t_in, t_out):
                if not t.done():
                    t.cancel()
            await asyncio.gather(t_in, t_out, return_exceptions=True)
            await self._cloturer(conn, agent, session, flags["completed"])

    async def _finaliser(
        self, conn: ClientConnection, state: FormState, session: LiveSession, statut: str
    ) -> None:
        payload = form_state_to_dict(state)
        await self._results.save(session.id, {"statut": statut, "formulaire": payload})
        await conn.send_json({"type": "final", "statut": statut, "form": payload})

    async def _cloturer(self, conn, agent, session: LiveSession, completed: bool) -> None:
        try:
            await agent.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Fermeture agent : %s", exc)
        try:
            await conn.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Fermeture connexion : %s", exc)
        session.statut = SessionStatus.COMPLETED if completed else SessionStatus.CLOSED
        try:
            await self._sessions.update(session)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Maj statut session %s impossible : %s", session.id, exc)
