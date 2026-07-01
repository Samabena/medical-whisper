// SDK serveur (Node) pour Voice-to-Form Live (INT-5.3).
// À utiliser depuis VOTRE backend : la clé API ne doit jamais atteindre le navigateur.

export interface SessionInfo {
  session_id: string;
  ws_url: string;
  token: string;
  language: "en" | "fr";
  expires_at: string;
  form_schema: Record<string, unknown>;
}

export class VoiceToFormError extends Error {
  constructor(public status: number, public payload: unknown) {
    super(`Voice-to-Form API ${status}`);
  }
}

export class VoiceToForm {
  constructor(private baseUrl: string, private apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: { "X-API-Key": this.apiKey, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = await resp.json().catch(() => null);
    if (!resp.ok) throw new VoiceToFormError(resp.status, payload);
    return payload as T;
  }

  /** Crée une session live et renvoie le jeton à transmettre au frontend. */
  createSession(formId: string): Promise<SessionInfo> {
    return this.request<SessionInfo>("POST", "/v1/integration/sessions", { form_id: formId });
  }

  /** Récupère le formulaire final (404 tant que la session n'est pas terminée). */
  getResult(sessionId: string): Promise<{ statut: string; formulaire: Record<string, unknown> }> {
    return this.request("GET", `/v1/integration/sessions/${sessionId}/result`);
  }
}
