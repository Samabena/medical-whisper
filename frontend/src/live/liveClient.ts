// Client live (navigateur) : ouvre le WebSocket, capture le micro (PCM 24 kHz),
// streame l'audio et expose les événements transcript / form_state / final.
import type { FieldDef } from "../api/types";

export interface FormStateMap {
  [field: string]: { valeur: unknown; confiance: string };
}

export interface LiveHandlers {
  onTranscript?: (speaker: string, text: string) => void;
  onFormState?: (state: FormStateMap) => void;
  onFinal?: (statut: string, form: FormStateMap) => void;
  onError?: (message: string) => void;
  onClose?: () => void;
}

export interface LiveSession {
  endTurn: () => void;
  sendText: (text: string) => void;
  stop: () => void;
}

export async function startLive(
  wsUrl: string,
  token: string,
  handlers: LiveHandlers
): Promise<LiveSession> {
  const ws = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`);
  ws.binaryType = "arraybuffer";

  // Lecture de la voix de l'agent : le serveur streame du PCM s16le mono BRUT (pas de WAV) au
  // fil de l'eau — plusieurs chunks par phrase. On convertit chaque chunk en AudioBuffer et on
  // les enchaîne sans recouvrement via un curseur de temps (lecture gapless « live »).
  const PIPER_RATE = 22050; // taux natif de la voix Piper fr_FR-siwis-medium (contrat TTS_SAMPLE_RATE)
  let playCtx: AudioContext | null = null;
  let nextPlayTime = 0;
  // Sources programmées encore en attente/lecture + compteur de génération. Un barge-in
  // (message serveur `interrupted`) doit POUVOIR VIDER cette file : sinon la voix continue
  // à débiter les phrases d'un tour précédent par-dessus le nouveau, et l'audio dérive de
  // plus en plus derrière le texte affiché (impression que « la voix ne dit pas le texte »).
  let scheduled: AudioBufferSourceNode[] = [];
  let audioGen = 0;
  const flushAgentAudio = () => {
    audioGen++;
    for (const s of scheduled) {
      try {
        s.stop();
      } catch {
        /* source déjà terminée */
      }
    }
    scheduled = [];
    nextPlayTime = playCtx ? playCtx.currentTime : 0;
  };
  const playAgentAudio = (data: ArrayBuffer) => {
    // Chunk PCM s16le → Float32 [-1, 1]. On tronque à un nombre pair d'octets par sûreté
    // (un échantillon = 2 octets) ; le backend garantit déjà des chunks pairs.
    const usable = data.byteLength - (data.byteLength % 2);
    if (usable <= 0) return;
    const pcm = new Int16Array(data, 0, usable / 2);
    if (!playCtx) playCtx = new AudioContext();
    if (playCtx.state === "suspended") void playCtx.resume();
    const gen = audioGen;
    const buf = playCtx.createBuffer(1, pcm.length, PIPER_RATE);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
    if (gen !== audioGen) return; // un flush (barge-in) est survenu entre-temps
    const src = playCtx.createBufferSource();
    src.buffer = buf; // AudioContext rééchantillonne 22050 → taux matériel automatiquement
    src.connect(playCtx.destination);
    const now = playCtx.currentTime;
    const start = Math.max(now, nextPlayTime);
    src.start(start);
    nextPlayTime = start + buf.duration;
    scheduled.push(src);
    src.onended = () => {
      scheduled = scheduled.filter((s) => s !== src);
    };
  };

  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      void playAgentAudio(ev.data); // voix de l'agent (TTS)
      return;
    }
    const msg = JSON.parse(ev.data as string);
    switch (msg.type) {
      case "transcript":
        handlers.onTranscript?.(msg.speaker, msg.text);
        break;
      case "form_state":
        handlers.onFormState?.(msg.state);
        break;
      case "final":
        handlers.onFinal?.(msg.statut ?? "termine", msg.form);
        break;
      case "interrupted":
        // Barge-in serveur : l'utilisateur a repris la parole. On coupe immédiatement la
        // voix de l'agent encore en file (le serveur a déjà cessé d'envoyer son audio).
        flushAgentAudio();
        break;
      case "error":
        handlers.onError?.(msg.message);
        break;
    }
  };
  ws.onclose = () => handlers.onClose?.();
  ws.onerror = () => handlers.onError?.("Erreur WebSocket");

  // Capture micro → PCM16 16 kHz. getUserMedia n'existe qu'en **contexte sécurisé**
  // (HTTPS ou http://localhost) : sur une origine HTTP non-localhost (réseau privé),
  // `navigator.mediaDevices` est absent et le navigateur bloque le micro.
  let ctx: AudioContext | null = null;
  let stream: MediaStream | null = null;
  let processor: ScriptProcessorNode | null = null;
  const origine = typeof window !== "undefined" ? window.location.origin : "?";
  const microDispo =
    typeof window !== "undefined" &&
    window.isSecureContext &&
    !!navigator.mediaDevices?.getUserMedia;
  if (!microDispo) {
    handlers.onError?.(
      `Micro bloqué : origine non sécurisée (${origine}). Le navigateur n'autorise le ` +
        "micro qu'en HTTPS ou via http://localhost. Solutions : servir le site en HTTPS, " +
        "y accéder par http://localhost (tunnel), ou autoriser cette origine dans " +
        "chrome://flags/#unsafely-treat-insecure-origin-as-secure puis relancer le " +
        "navigateur. Le test continue sans audio (saisie texte possible)."
    );
  } else {
    try {
      // echoCancellation : ESSENTIEL pour le barge-in. Sans casque, le micro capte la voix
      // de l'agent dans les haut-parleurs → le VAD serveur la prendrait pour une reprise de
      // parole et couperait l'agent en boucle. L'AEC du navigateur retire ce que l'on joue.
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      // IMPORTANT : beaucoup de navigateurs IGNORENT `sampleRate` et capturent au taux
      // matériel (souvent 48 kHz). On lit donc le taux RÉEL (ctx.sampleRate) et on
      // rééchantillonne nous-mêmes vers 16 kHz (attendu par le STT) — fiable partout.
      ctx = new AudioContext();
      const inRate = ctx.sampleRate;
      const OUT_RATE = 16000;
      const step = inRate / OUT_RATE;
      const source = ctx.createMediaStreamSource(stream);
      processor = ctx.createScriptProcessor(4096, 1, 1);
      source.connect(processor);
      processor.connect(ctx.destination);
      let carry = new Float32Array(0); // échantillons restants entre deux blocs
      let readPos = 0; // position de lecture fractionnaire conservée d'un bloc à l'autre
      // --- VAD client : ne streamer que la PAROLE ----------------------------------------
      // Le micro tourne en continu ; envoyer le silence à Whisper le fait HALLUCINER du texte
      // (« Merci. », « Sous-titres… ») → l'agent répond à du vide et le formulaire se remplit
      // de valeurs inventées. On n'émet donc que si l'énergie dépasse un seuil, avec un
      // PRÉ-ROLL (contexte avant l'attaque du mot, pour ne pas couper le début) et un HANGOVER
      // (queue de mot + silence final, pour que le serveur détecte la fin de tour).
      // Seuil d'énergie (RMS échantillons 16 bits). Avec noiseSuppression, le silence tombe
      // très bas (~<50) alors que la parole est nettement au-dessus : un seuil modéré sépare
      // les deux sans couper la voix. ↑ = moins sensible (risque de couper la parole).
      const VAD_RMS = 300;
      const PREROLL_FRAMES = 4; // ~0,3 s de contexte envoyé quand la parole démarre
      const HANGOVER_FRAMES = 10; // ~0,85 s encore envoyés après la fin de parole
      let hangover = 0;
      let preroll: ArrayBuffer[] = [];
      let vadFrames = 0; // pour throttler le log de calibration
      const rms16 = (a: Int16Array) => {
        let s = 0;
        for (let k = 0; k < a.length; k++) s += a[k] * a[k];
        return a.length ? Math.sqrt(s / a.length) : 0;
      };
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const cur = e.inputBuffer.getChannelData(0);
        const data = new Float32Array(carry.length + cur.length);
        data.set(carry, 0);
        data.set(cur, carry.length);
        const out: number[] = [];
        let i = readPos;
        for (; i + 1 < data.length; i += step) {
          const i0 = i | 0;
          const f = i - i0;
          out.push(data[i0] * (1 - f) + data[i0 + 1] * f); // interpolation linéaire
        }
        const consumed = i | 0;
        carry = data.slice(consumed);
        readPos = i - consumed;
        const buf = new Int16Array(out.length);
        for (let k = 0; k < out.length; k++) {
          buf[k] = Math.max(-1, Math.min(1, out[k])) * 0x7fff;
        }
        if (!buf.length) return;
        const energy = rms16(buf);
        // Log de calibration (~1,4 s) : compare l'énergie de ta voix au seuil dans la console.
        if (++vadFrames % 16 === 0) {
          console.debug(`[vad] energy≈${energy | 0} (seuil ${VAD_RMS}, ${energy >= VAD_RMS ? "PAROLE" : "silence"})`);
        }
        if (energy >= VAD_RMS) {
          if (hangover === 0) console.debug(`[vad] → parole détectée (energy=${energy | 0}), envoi au STT`);
          for (const p of preroll) ws.send(p); // contexte avant l'attaque du mot
          preroll = [];
          ws.send(buf.buffer);
          hangover = HANGOVER_FRAMES;
        } else if (hangover > 0) {
          ws.send(buf.buffer); // queue de parole + silence final (fin de tour côté serveur)
          hangover--;
          // Fin de parole détectée par le VAD client : on demande au serveur de finaliser
          // MAINTENANT (END_OF_AUDIO), sans attendre son propre compteur de silence. Sinon le
          // serveur (SILENCE_MS) exige plus de silence continu que ce hangover n'en envoie
          // (~0,85 s) et ne finalise qu'au garde-fou des 30 s → latence énorme.
          if (hangover === 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "end_turn" }));
          }
        } else {
          preroll.push(buf.buffer); // silence : on ne garde qu'un court contexte glissant
          if (preroll.length > PREROLL_FRAMES) preroll.shift();
        }
      };
    } catch (err) {
      const nom = (err as { name?: string } | null)?.name;
      const detail =
        nom === "NotAllowedError" || nom === "SecurityError"
          ? "accès refusé — autorisez le micro pour ce site"
          : nom === "NotFoundError" || nom === "OverconstrainedError"
            ? "aucun micro détecté"
            : (nom ?? "erreur inconnue");
      handlers.onError?.(`Micro indisponible (${detail}). Le test continue sans audio.`);
    }
  }

  const cleanup = () => {
    processor?.disconnect();
    stream?.getTracks().forEach((t) => t.stop());
    ctx?.close();
    playCtx?.close();
    playCtx = null;
  };

  return {
    endTurn: () => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "end_turn" }));
    },
    sendText: (text: string) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "user_text", text }));
    },
    stop: () => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "stop" }));
      cleanup();
      ws.close();
    },
  };
}

export function emptyState(fields: FieldDef[]): FormStateMap {
  const s: FormStateMap = {};
  for (const f of fields) s[f.name] = { valeur: null, confiance: "manquant" };
  return s;
}
