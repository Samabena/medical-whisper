// Helper navigateur pour le dialogue vocal temps réel (INT-5.3).
//
// ⚠️ Implémentation de RÉFÉRENCE alignée sur le protocole de messages prévu à l'EPIC 7
// (relais WebSocket full-duplex). À finaliser/valider quand l'endpoint /v1/live sera livré.

export interface FormState {
  [field: string]: { valeur: unknown; confiance: "confiant" | "incertain" | "manquant" };
}

export interface LiveSession {
  onFormState(cb: (state: FormState) => void): void;
  onAgentAudio(cb: (chunk: ArrayBuffer) => void): void;
  onFinal(cb: (form: Record<string, unknown>) => void): void;
  stop(): void;
}

/** Ouvre la session live : capture le micro, streame l'audio, reçoit form_state + voix. */
export async function startLiveSession(wsUrl: string, token: string): Promise<LiveSession> {
  const ws = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`);
  ws.binaryType = "arraybuffer";

  const formStateCbs: Array<(s: FormState) => void> = [];
  const audioCbs: Array<(c: ArrayBuffer) => void> = [];
  const finalCbs: Array<(f: Record<string, unknown>) => void> = [];

  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      audioCbs.forEach((cb) => cb(ev.data));
      return;
    }
    const msg = JSON.parse(ev.data);
    if (msg.type === "form_state") formStateCbs.forEach((cb) => cb(msg.state));
    else if (msg.type === "final") finalCbs.forEach((cb) => cb(msg.form));
  };

  // Capture micro → trames audio 24 kHz vers le serveur.
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ctx = new AudioContext({ sampleRate: 24_000 });
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(2048, 1, 1);
  source.connect(processor);
  processor.connect(ctx.destination);
  processor.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const pcm = e.inputBuffer.getChannelData(0);
    const buf = new Int16Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) buf[i] = Math.max(-1, Math.min(1, pcm[i])) * 0x7fff;
    ws.send(buf.buffer);
  };

  return {
    onFormState: (cb) => formStateCbs.push(cb),
    onAgentAudio: (cb) => audioCbs.push(cb),
    onFinal: (cb) => finalCbs.push(cb),
    stop: () => {
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
      ws.close();
    },
  };
}
