# Voice-to-Form **Live**

Service B2B de remplissage de **formulaires médicaux par dialogue vocal temps réel**.
Une app cliente intègre notre API ; le médecin parle, un agent vocal full-duplex mène la
conversation, et le formulaire se remplit en direct par extraction LLM. Pas d'UI finale de
notre côté — les clients ont la leur.

Architecture cible : **« sandwich » CPU** (sans GPU) — STT (faster-whisper) → agent (Ollama)
→ TTS (Piper), avec un extracteur LLM lisant le transcript.

> Pivot depuis le pipeline turn-based v1 (archivé : `docs/BACKLOG_v1_voice_to_form_archive.md`).

## Stack
React + TS (admin) · FastAPI async (clean architecture) · PostgreSQL · Redis ·
faster-whisper (STT, CPU) · Piper (TTS, CPU) · Ollama (agent + extraction) ·
Docker Compose · Caddy (TLS).

## Documentation
| Doc | Contenu |
|-----|---------|
| `DOCUMENTATION_TECHNIQUE.md` | Doc technique consolidée : archi, composants Docker, API, données, config, sécurité |
| `ARCHITECTURE.md` | Couches clean archi, flux jeton éphémère, sécurité, conformité santé |
| `BACKLOG.md` | EPICs 0–11 (tous implémentés) |
| `RUNBOOK.md` | Exploitation : dev/voice/prod (CPU), migrations, sauvegarde, dépannage |
| `sdk/README.md` | SDK Python/TS + intégration cliente |

## Démarrage rapide (dev, sans GPU)
```bash
cp .env.example .env     # renseigner POSTGRES_PASSWORD, JWT_SECRET (≥32), ADMIN_PASSWORD
docker compose --profile dev up --build
```
Admin : http://localhost:5173 · API : http://localhost:8000/health · Swagger : `/docs`.
Le dialogue live tourne avec l'**agent stub** (sans GPU ni LLM).

Tests backend :
```bash
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -e ".[dev]" && pytest
```

---

## Intégration cliente en < 30 min

Modèle **server-to-server + jeton éphémère** : la clé API reste sur le backend client ;
son frontend ouvre le WebSocket avec un jeton court. (Détails et SDK : `sdk/README.md`.)

### 1 — Côté plateforme : créer un compte + une clé (admin)
Via le portail admin (`/`) ou l'API : créer le compte (langue en/fr), générer une **clé API**
(affichée une seule fois), construire et **publier** un formulaire.

### 2 — Backend client : démarrer une session
```bash
curl -X POST https://api.voice-to-form/v1/integration/sessions \
  -H "X-API-Key: $CLE" -H "Content-Type: application/json" \
  -d '{"form_id":"consultation"}'
# → { session_id, ws_url, token, language, form_schema, expires_at }
```

### 3 — Frontend client : dialogue temps réel
```ts
const ws = new WebSocket(`${ws_url}?token=${token}`);   // micro 24 kHz ↔ voix de l'agent
ws.onmessage = (e) => {/* {type:"form_state"} → MAJ formulaire en direct ; {type:"final"} → fini */};
```

### 4 — Backend client : récupérer le résultat
```bash
curl https://api.voice-to-form/v1/integration/sessions/$SID/result -H "X-API-Key: $CLE"
# → { statut, formulaire }
```

---

## Statuts & erreurs
| `statut` (résultat) | Sens |
|---------------------|------|
| `termine` | Champs requis complétés |
| `incomplet` | Clôture après trop de tours (champs requis à vérifier) |

| Code | Sens |
|------|------|
| 401 `non_autorise` | clé API / jeton invalide |
| 404 `non_trouve` | formulaire / session inconnu |
| 422 `validation` | requête invalide |
| 429 `quota_depasse` | limite de débit |
| 503 `service_indisponible` | modèle / LLM injoignable |

WebSocket : `4401` jeton invalide/expiré/rejoué · `4403` origine refusée · `4404` session introuvable.

## Données de santé
Aucune persistance d'audio ni de transcript. La base ne stocke que des métadonnées
(comptes, clés, formulaires, usage). Le formulaire final est purgé après une rétention courte.
Voir `ARCHITECTURE.md §7`.
