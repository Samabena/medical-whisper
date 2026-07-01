import { useMemo, useRef, useState } from "react";
import { integrationApi } from "../api/client";
import type { FieldDef } from "../api/types";
import { startLive, type FormStateMap, type LiveSession } from "../live/liveClient";
import { Badge, Button, Card, CardHeader, EmptyState, Field, PageHeader } from "../components/ui";
import { IconConsole, IconPlay, IconSkip, IconStop } from "../components/Icons";
import { useToast } from "../components/Toast";

type Status = "idle" | "connecting" | "live" | "done";

const STATUS_LABEL: Record<Status, string> = {
  idle: "En attente", connecting: "Connexion…", live: "En direct", done: "Terminé",
};

export function LiveConsolePage() {
  const [apiKey, setApiKey] = useState("");
  const [forms, setForms] = useState<{ form_id: string; titre: string }[]>([]);
  const [formId, setFormId] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [transcript, setTranscript] = useState<{ who: string; text: string }[]>([]);
  const [state, setState] = useState<FormStateMap>({});
  const [fields, setFields] = useState<FieldDef[]>([]);
  const [utterance, setUtterance] = useState("");
  const sessionRef = useRef<LiveSession | null>(null);
  const toast = useToast();

  const loadForms = async () => {
    try {
      const f = await integrationApi.listForms(apiKey);
      setForms(f);
      if (f[0]) setFormId(f[0].form_id);
      if (f.length === 0) toast("info", "Aucun formulaire publié pour cette clé.");
    } catch (e: any) {
      toast("error", e?.message ?? "Clé invalide ou API injoignable.");
    }
  };

  const start = async () => {
    setStatus("connecting");
    setTranscript([]);
    setState({});
    try {
      const session = await integrationApi.createSession(apiKey, formId);
      setFields(session.form_schema.fields || []);
      sessionRef.current = await startLive(session.ws_url, session.token, {
        onTranscript: (who, text) => text && setTranscript((t) => [...t, { who, text }]),
        onFormState: (s) => setState(s),
        onFinal: (statut, form) => {
          setState(form);
          setStatus("done");
          toast(statut === "termine" ? "success" : "info", `Session terminée (${statut}).`);
        },
        onError: (m) => toast("error", m),
        onClose: () => setStatus((s) => (s === "done" ? s : "idle")),
      });
      setStatus("live");
    } catch (e: any) {
      setStatus("idle");
      toast("error", e?.message ?? "Démarrage impossible.");
    }
  };

  const endTurn = () => sessionRef.current?.endTurn();
  const say = () => {
    const t = utterance.trim();
    if (!t) return;
    sessionRef.current?.sendText(t);
    setUtterance("");
  };
  const stop = () => {
    sessionRef.current?.stop();
    setStatus("done");
  };

  const running = status === "live";
  const required = useMemo(() => fields.filter((f) => f.required), [fields]);
  const filled = required.filter((f) => state[f.name]?.confiance === "confiant").length;
  const pct = required.length ? Math.round((filled / required.length) * 100) : 0;

  return (
    <div>
      <PageHeader
        title="Console de test live"
        sub="Simulez une intégration cliente : la clé API d'un compte pilote un vrai dialogue vocal."
        actions={
          <span className={`status-pill ${status}`}>
            <span className="status-dot" /> {STATUS_LABEL[status]}
          </span>
        }
      />

      <Card>
        <div className="card-body">
          <div className="session-bar">
            <input className="input flex-1" placeholder="Clé API du compte (X-API-Key)" value={apiKey} onChange={(e) => setApiKey(e.target.value)} disabled={running} />
            <Button variant="secondary" onClick={loadForms} disabled={!apiKey || running}>Charger</Button>
            <select className="select" value={formId} onChange={(e) => setFormId(e.target.value)} disabled={running || forms.length === 0} style={{ minWidth: 180 }}>
              {forms.length === 0 ? <option value="">— formulaires —</option> : forms.map((f) => <option key={f.form_id} value={f.form_id}>{f.titre}</option>)}
            </select>
            {!running ? (
              <Button variant="primary" onClick={start} disabled={!formId}><IconPlay size={16} /> Démarrer</Button>
            ) : (
              <>
                <Button variant="secondary" onClick={endTurn}><IconSkip size={16} /> Fin de tour</Button>
                <Button variant="danger" onClick={stop}><IconStop size={16} /> Arrêter</Button>
              </>
            )}
          </div>
          <p className="subtle mt-2">
            Mode démo (sans GPU) : la reconnaissance vocale réelle nécessite le modèle PersonaPlex.
            Ici, <strong>tape ce que dirait le médecin</strong> dans le champ de conversation pour remplir le formulaire.
          </p>
        </div>
      </Card>

      {status === "idle" && transcript.length === 0 ? (
        <Card>
          <EmptyState
            icon={<IconConsole size={24} />}
            title="Prêt à tester"
            sub="Collez une clé API, chargez les formulaires publiés, puis démarrez une session. Autorisez le micro pour parler à l'agent."
          />
        </Card>
      ) : (
        <div className="console-grid">
          <Card>
            <CardHeader title="Conversation" sub="Transcript temps réel (agent ↔ utilisateur)." />
            <div className="card-body">
              {transcript.length === 0 ? (
                <p className="muted">En attente du premier échange…</p>
              ) : (
                <div className="chat">
                  {transcript.map((t, i) => (
                    <div key={i} className={`bubble ${t.who === "user" ? "user" : "agent"}`}>
                      <div className="who">{t.who === "user" ? "Vous" : "Agent"}</div>
                      {t.text}
                    </div>
                  ))}
                </div>
              )}

              {running && (
                <div className="row mt-4" style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
                  <input
                    className="input flex-1"
                    placeholder="Ex. nom: Dupont, diagnostic: migraine"
                    value={utterance}
                    onChange={(e) => setUtterance(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && say()}
                  />
                  <Button variant="primary" onClick={say} disabled={!utterance.trim()}>Envoyer</Button>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Formulaire" sub={`${filled}/${required.length} champ(s) requis`} />
            <div className="card-body">
              <div className="progress" style={{ marginBottom: 14 }}><span style={{ width: `${pct}%` }} /></div>
              <div className="field-list">
                {fields.map((f) => {
                  const v = state[f.name];
                  const conf = v?.confiance ?? "manquant";
                  const tone = conf === "confiant" ? "success" : conf === "incertain" ? "warning" : "neutral";
                  return (
                    <div className="field-item" key={f.name}>
                      <div className="field-meta">
                        <div className="field-name">{f.label} {f.required && <span style={{ color: "var(--danger)" }}>*</span>}</div>
                        <div className="field-val">{v?.valeur != null && v.valeur !== "" ? String(v.valeur) : "—"}</div>
                      </div>
                      <Badge tone={tone as any} dot>{conf}</Badge>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
