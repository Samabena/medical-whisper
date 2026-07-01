"""Contrôleur de tour de parole & barge-in (LIVE-7.4).

Quand l'agent « parle » (génération LLM + synthèse + envoi audio), l'utilisateur doit
pouvoir **l'interrompre** : dès qu'il reprend la parole, on **annule** proprement la
tâche de sortie en cours (agent + file TTS) pour réagir tout de suite. C'est le
*barge-in*, levier majeur de réactivité **perçue**.

Primitive `asyncio` pure (aucune dépendance infra) : elle encapsule au plus **une**
tâche de sortie active, l'annule sur demande, et garantit l'absence de tâche orpheline.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class TurnController:
    """Gère la tâche de sortie agent courante et son annulation (barge-in)."""

    def __init__(self, *, barge_in: bool = True) -> None:
        self._barge_in = barge_in
        self._task: asyncio.Task | None = None

    @property
    def speaking(self) -> bool:
        """Vrai si une sortie agent est en cours."""
        return self._task is not None and not self._task.done()

    def start(self, coro: Awaitable[None]) -> None:
        """Démarre une sortie agent. Toute sortie précédente non finie est annulée."""
        self._cancel_current()
        self._task = asyncio.ensure_future(coro)

    async def on_user_speech(self) -> bool:
        """Reprise de parole : interrompt la sortie en cours si barge-in actif.

        Renvoie `True` si une sortie a effectivement été interrompue.
        """
        if not self._barge_in or not self.speaking:
            return False
        await self._await_cancel()
        return True

    async def wait(self) -> None:
        """Attend la fin naturelle de la sortie courante (sans l'annuler)."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    async def close(self) -> None:
        """Annule et draine la sortie en cours (fermeture de session)."""
        await self._await_cancel()

    def _cancel_current(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _await_cancel(self) -> None:
        task = self._task
        if task is None:
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self._task = None


async def run_cancellable(
    body: Callable[[], Awaitable[None]],
    *,
    on_cancel: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Exécute `body`, en appelant `on_cancel` (nettoyage) si la tâche est annulée.

    Utile pour libérer la file TTS / fermer un flux quand un barge-in survient.
    """
    try:
        await body()
    except asyncio.CancelledError:
        if on_cancel is not None:
            await on_cancel()
        raise
