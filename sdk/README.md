# SDK & Intégration — Voice-to-Form Live

> Objectif : intégrer le remplissage vocal en **moins de 30 minutes**, sans jamais
> exposer votre clé API au navigateur.

## Le modèle d'intégration (server-to-server + jeton éphémère)

```
1. VOTRE BACKEND ──POST /v1/integration/sessions (X-API-Key)──► Voice-to-Form
                 ◄── { session_id, ws_url, token, language, form_schema }

2. VOTRE FRONTEND ──wss ws_url ?token=…──► Voice-to-Form   (micro ↔ voix, temps réel)
                 ◄── form_state (champs remplis en direct), audio de l'agent

3. VOTRE BACKEND ──GET /v1/integration/sessions/{id}/result (X-API-Key)──► formulaire final
```

- La **clé API** reste sur votre backend (étapes 1 et 3).
- Le **jeton** (court, ~60 s) autorise une seule session WebSocket côté frontend (étape 2).

---

## Étape 1 — Démarrer une session (votre backend)

### Python
```python
from voice_to_form_client import VoiceToFormClient

vtf = VoiceToFormClient("https://api.voice-to-form.example", api_key="VOTRE_CLE")
session = vtf.create_session(form_id="consultation")
# → renvoyez session["ws_url"], session["token"], session["form_schema"] à votre frontend
```

### TypeScript / Node
```ts
import { VoiceToForm } from "./server";

const vtf = new VoiceToForm("https://api.voice-to-form.example", "VOTRE_CLE");
const session = await vtf.createSession("consultation");
```

## Étape 2 — Dialogue vocal (votre frontend)
```ts
import { startLiveSession } from "./browser";

const live = await startLiveSession(session.ws_url, session.token);
live.onFormState((state) => renderForm(state));   // champs remplis en direct
live.onAgentAudio((chunk) => play(chunk));         // voix de l'agent
// live.stop() pour terminer
```

## Étape 3 — Récupérer le résultat (votre backend)
```python
result = vtf.get_result(session["session_id"])
# → { "statut": "termine", "formulaire": { ... } }
```

---

## Référence des endpoints

| Méthode | Endpoint | Auth | Rôle |
|--------|----------|------|------|
| POST | `/v1/integration/sessions` | `X-API-Key` | Crée une session + jeton |
| GET  | `/v1/integration/sessions/{id}/result` | `X-API-Key` | Formulaire final |
| WS   | `/v1/live/{session_id}?token=…` | jeton éphémère | Dialogue temps réel (EPIC 7) |

> ⚠️ Le transport WebSocket (étape 2) est finalisé à l'EPIC 7 ; `browser.ts` en fournit
> une implémentation de référence alignée sur le protocole de messages prévu.
