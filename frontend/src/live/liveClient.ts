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

  // Lecture de la voix de l'agent : chaque frame binaire est un WAV (Piper) complet.
  // On les décode et on les enchaîne sans recouvrement via un curseur de temps.
  let playCtx: AudioContext | null = null;
  let nextPlayTime = 0;
  // Sources programmées encore en attente/lecture + compteur de génération. Un barge-in
  // (message serveur `interrupted`) doit POUVOIR VIDER cette file : sinon la voix continue
  // à débiter les phrases d'un tour précédent par-dessus le nouveau, et l'audio dérive de
  // plus en plus derrière le texte affiché (impression que « la voix ne dit pas le texte »).
  let scheduled: AudioBufferSourceNode[] = [];
  let audioGen = 0;
  const flushAgentAudio = () => {
    audioGen++; // invalide les décodages encore en vol (cf. playAgentAudio)
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
  const playAgentAudio = async (data: ArrayBuffer) => {
    const gen = audioGen;
    try {
      if (!playCtx) playCtx = new AudioContext();
      if (playCtx.state === "suspended") await playCtx.resume();
      const buf = await playCtx.decodeAudioData(data.slice(0));
      if (gen !== audioGen) return; // un flush (barge-in) est survenu pendant le décodage
      const src = playCtx.createBufferSource();
      src.buffer = buf;
      src.connect(playCtx.destination);
      const now = playCtx.currentTime;
      const start = Math.max(now, nextPlayTime);
      src.start(start);
      nextPlayTime = start + buf.duration;
      scheduled.push(src);
      src.onended = () => {
        scheduled = scheduled.filter((s) => s !== src);
      };
    } catch (err) {
      // Ne plus avaler silencieusement : une frame non décodée = une phrase affichée mais
      // jamais entendue. On la trace pour pouvoir diagnostiquer un éventuel souci de format.
      console.warn("[live] frame audio agent non décodable, ignorée :", err);
    }
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
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        if (buf.length) ws.send(buf.buffer);
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
