# Documentation technique — Voice-to-Form **Live**

> Service B2B de remplissage de **formulaires médicaux par dialogue vocal temps réel**.
> Version backend : **2.0.0** · Architecture : **« sandwich » CPU** (sans GPU).
>
> Documents liés : `ARCHITECTURE.md` (détail des couches) · `RUNBOOK.md` (exploitation)
> · `BACKLOG.md` (EPICs) · `sdk/README.md` (intégration cliente) · `README.md` (démarrage).

---

## 1. Vue d'ensemble

Une application cliente intègre notre API ; le médecin parle, un **agent vocal full-duplex**
mène la conversation, et le **formulaire se remplit en direct** par extraction LLM du transcript.
Nous ne fournissons pas d'UI finale — chaque client a la sienne (nous exposons une API + un
portail d'administration).

### Le pipeline « sandwich » (CPU, sans GPU)
Le cœur temps réel décompose la parole en trois maillons remplaçables :

```
  micro client (PCM 24 kHz)                                    voix de l'agent (WAV)
        │                                                              ▲
        ▼                                                              │
  ┌───────────┐   texte    ┌───────────────────┐   phrases   ┌────────────────┐
  │   STT     │──────────► │  Agent (LLM)       │───────────►│   TTS (Piper)  │
  │faster-    │  final     │  Ollama streaming  │  segmentées │  synthèse par  │
  │whisper WS │            └───────────────────┘             │  phrase        │
  └───────────┘                     │ transcript                └────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │ Extracteur (LLM)    │  → form_state {valeur, confiance}
                          │ Ollama structured   │     poussé au client en direct
                          └─────────────────────┘
```

- **STT** : serveur WebSocket **WhisperLive en ligne de l'équipe** (`ws://srv-team-ia:9300`),
  basé sur faster-whisper (handshake JSON + audio float32, prompt de domaine médical). Le backend
  s'y connecte via l'adaptateur `whisperlive` ; aucun serveur STT local dans la stack.
- **Agent** : réponse conversationnelle courte (1–2 phrases) générée en streaming par **Ollama**.
- **TTS** : `piper-server/` — serveur HTTP encapsulant **Piper** (voix FR `fr_FR-siwis-medium`).
- **Extracteur** : lit le transcript et remplit le formulaire via **Ollama** en sorties structurées
  (JSON schema), en fusionnant sans écraser les champs déjà « confiants ».

### Stack technique
| Domaine | Technologie |
|---------|-------------|
| Backend | Python 3.11+, FastAPI async, clean architecture |
| Base de données | PostgreSQL (asyncpg) + SQLAlchemy 2.0 async + Alembic |
| Cache / éphémère | Redis (jetons, pub/sub, rate-limit) |
| Frontend admin | React + TypeScript (Vite) → nginx |
| STT | faster-whisper (CPU) via WebSocket type WhisperLive |
| TTS | Piper (CPU) via serveur HTTP dédié |
| Agent + extraction | Ollama Cloud (`https://ollama.com`, clé API) |
| Reverse-proxy / TLS | Caddy |
| Orchestration | Docker Compose (profils dev / voice / prod) |

---

## 2. Architecture logicielle (clean architecture)

Le backend (`backend/app/`) applique la **règle de dépendance** : les couches internes ignorent
les couches externes. Un test AST garde-fou vérifie que le domaine ne dépend d'aucune infra.

```
interface  ─► application ─► domain            (dépendances pointant vers l'intérieur)
     └────────► infrastructure ─┘              (l'infra implémente les ports de l'application)
```

| Couche | Rôle | Contenu clé |
|--------|------|-------------|
| **domain** | Entités & règles pures (aucune dépendance externe) | dataclasses `Account`, `ApiKey`, `FormDefinition`, `FormField`, `LiveSession`, `FormState`, `FieldValue`, `UsageRecord` ; enums `Language`, `Confidence`, `FieldType`, `FormStatus`, `SessionStatus` ; erreurs métier |
| **application** | Cas d'usage + **ports** (Protocols) | orchestrateur `RunLiveDialogue`, `FormExtractor`, cas d'usage admin/intégration, segmenteur de phrases, builders de schéma/persona ; ports repos, speech, STT, TTS, extraction, tokens, métriques, etc. |
| **infrastructure** | Adapters concrets des ports | STT/TTS/agent/extraction (voir §3.2), SQLAlchemy (models/repos/mappers), sécurité (JWT, argon2, SHA-256), observabilité, rate-limit, result store |
| **interface** | Entrées HTTP/WS + composition root | `main.py` (factory FastAPI), routers REST + WebSocket, middlewares, `deps.py` (injection de dépendances) |

### Injection de dépendances (`interface/deps.py`)
- **Singletons** (LRU) : `speech_agent`, `token_service`, `result_store`, `metrics`, `key_hasher`,
  `replay_guard`, `extractor`, `password_hasher`, `admin_token_service`, `rate_limiter`.
- **Par requête** : `db_session` (AsyncSession) + repos (`account_repo`, `apikey_repo`, `form_repo`,
  `session_repo`, `usage_repo`).
- **Auth** : `require_admin` (jeton admin), `current_account` (clé API → compte).

Tout cas d'usage dépend d'un **port**, jamais d'une implémentation → backends interchangeables et
testables avec des faux (stubs).

---

## 3. Composants de déploiement (Docker)

Chaque serveur est un **composant Docker distinct**, orchestré par `docker-compose.yml`.

| Service | Image / build | Port | Profils | Rôle |
|---------|---------------|------|---------|------|
| `backend` | `./backend/Dockerfile` | 8000 | dev, prod | API FastAPI (REST + WebSocket live) |
| `frontend` | `./frontend/Dockerfile` | 5173→80 | dev, prod | Portail admin React (nginx) |
| `db` | `postgres:16-alpine` | interne | dev, prod | Métadonnées (comptes, clés, formulaires, usage) |
| `redis` | `redis:7-alpine` | interne | dev, prod | Jetons / pub-sub / rate-limit |
| `migrate` | `./backend` (one-shot) | — | dev, prod | `alembic upgrade head` (bloquant avant backend) |
| `piper` | `./piper-server/Dockerfile` | 5000 | voice, prod | TTS Piper (HTTP) |
| `proxy` | `caddy:2-alpine` | 80/443 | prod | Reverse-proxy + TLS automatique |

> Agent + extraction LLM = **Ollama Cloud** (`OLLAMA_HOST=https://ollama.com` + `OLLAMA_API_KEY`) : pas de service `ollama` dans la stack.

### 3.1 Profils Compose
- **`dev`** — pile minimale hors-ligne (`backend`+`db`+`redis`+`frontend`+`migrate`) avec
  `SPEECH_AGENT=stub`. Aucun modèle, aucun GPU. `docker compose --profile dev up --build`.
- **`voice`** — ajoute le TTS local `piper`. Se combine avec `dev`
  pour tester en local : `docker compose --profile dev --profile voice up`. Le STT (serveur en
  ligne `ws://srv-team-ia:9300`) et le LLM (Ollama Cloud) sont des services externes, pas locaux.
- **`prod`** — pile complète + `proxy` TLS. `docker compose --profile prod up --build -d`.

> La bascule stub ↔ sandwich se fait par **`SPEECH_AGENT` dans `.env`**, pas par un profil.
> Le backend appelle `piper`, le STT en ligne et Ollama Cloud **paresseusement** (au fil du
> dialogue) : le profil `dev` reste donc autonome sans ces services.

### 3.2 Backends interchangeables (pilotés par `.env`)
| Maillon | Var | Valeurs |
|---------|-----|---------|
| Agent vocal | `SPEECH_AGENT` | `stub` (dev) · `sandwich` (prod) · `llm` (texte seul) |
| STT | `STT_BACKEND` | `stub` · `whisperlive` (→ serveur en ligne `ws://srv-team-ia:9300`) |
| TTS | `TTS_BACKEND` | `stub` · `piper_http` (→ `piper:5000`, recommandé) · `piper` (binaire local) |
| Agent LLM | `AGENT_BACKEND` | `scripted` (dev) · `ollama` (streaming) |
| Extraction | `EXTRACTOR_BACKEND` | `null` (dev) · `keyword` · `ollama` |

**Le serveur STT** (WhisperLive en ligne de l'équipe, `ws://srv-team-ia:9300`) : à la connexion le
client envoie une config JSON, le serveur répond `SERVER_READY`, puis reçoit de l'audio
**float32 16 kHz**, applique un VAD par énergie (RMS) + silence, transcrit par lots, filtre les
hallucinations de sous-titres, et émet des segments `{text, completed, words}`. Côté backend,
l'adaptateur `whisperlive` (`app/infrastructure/stt/whisperlive.py`) parle ce protocole.

**Le serveur Piper** (`piper-server/server.py`) : `POST /synthesize {text, voice}` → `audio/wav`.
La voix `.onnx` (~63 Mo) est fournie par **volume** (`./voices:/voices:ro`) et non baked dans
l'image. Adapter côté backend : `app/infrastructure/tts/piper_http.py` (`PiperHttpTts`).

---

## 4. Flux fonctionnels

### 4.1 Intégration server-to-server + jeton éphémère
La **clé API reste sur le backend client** ; son frontend ouvre le WebSocket avec un **jeton JWT
court** (défaut 60 s), jamais la clé API dans le navigateur.

```
Backend client ──(X-API-Key)──► POST /v1/integration/sessions
                                      │  crée LiveSession + mint jeton éphémère (aud=session, jti)
                                      ▼
        { session_id, ws_url, token, language, form_schema, expires_at }
                                      │
Frontend client ──(ws_url?token=…)──► WS /v1/live/{session_id}
                                      │  vérifie signature+exp+aud+anti-rejeu(jti)+Origin
                                      │  dialogue full-duplex (audio ↔, transcript, form_state)
                                      ▼
Backend client ──(X-API-Key)──► GET /v1/integration/sessions/{id}/result → { statut, formulaire }
```

### 4.2 Boucle de dialogue live (`RunLiveDialogue`)
Deux boucles concurrentes relayées par l'orchestrateur :
- **client → agent** : trames audio + messages de contrôle (`end_turn`, `user_text`).
- **agent → client** : audio de l'agent, transcrits (`user`/`agent`), `form_state`, `final`.

À chaque transcript utilisateur, l'**extracteur** met à jour le `FormState` (fusion sans écraser
un champ confiant) et le nouvel état est poussé au client. La **complétion** (tous les champs
requis « confiants ») clôt la session en `termine` ; le garde-fou `MAX_USER_TURNS` clôt en
`incomplet`. Leviers de latence : déclenchement spéculatif, barge-in, backchannel, TTS par phrase,
cache de prompt (cf. `ARCHITECTURE.md §5`).

---

## 5. API

Base d'URL en prod : `https://$DOMAIN`. Swagger : `/docs`.

### 5.1 Intégration cliente — `/v1/integration` (auth `X-API-Key`)
| Méthode | Chemin | Rôle |
|---------|--------|------|
| GET | `/forms` | Liste des formulaires **publiés** du compte |
| GET | `/forms/{form_id}` | Schéma d'un formulaire publié |
| POST | `/sessions` | Crée une session live + jeton éphémère |
| GET | `/sessions/{session_id}/result` | Récupère le formulaire final |

### 5.2 WebSocket live — `/v1/live/{session_id}?token=…`
Messages entrants : trames binaires audio, `{"type":"end_turn"}`, `{"type":"user_text","text":…}`.
Messages sortants : `{"type":"transcript",…}`, `{"type":"form_state","values":{champ:{valeur,confiance}}}`,
`{"type":"final",…}`, audio binaire de l'agent.
Codes de fermeture : `4401` jeton invalide/expiré/rejoué · `4403` origine refusée · `4404` session/compte/formulaire introuvable.

### 5.3 Admin — `/admin/api` (auth JWT admin `require_admin`)
| Domaine | Endpoints |
|---------|-----------|
| Auth | `POST /login`, `POST /refresh`, `GET /me` |
| Comptes | `POST/GET /accounts`, `GET/PATCH /accounts/{id}` (langue, persona, voix, origines, actif) |
| Clés API | `POST/GET /accounts/{id}/keys`, `DELETE /accounts/{id}/keys/{key_id}` (clé en clair affichée 1×) |
| Formulaires | `POST/GET /accounts/{id}/forms`, `GET/PATCH …/{form_id}`, `POST …/{form_id}/publish` (versionnage draft→published) |
| Usage | `GET /accounts/{id}/usage` |

### 5.4 Ops
| Méthode | Chemin | Rôle |
|---------|--------|------|
| GET | `/health` | `{"status":"ok"}` (exempté du rate-limit) |
| GET | `/metrics` | Snapshot d'observabilité (agrégats, **sans PHI**) |

### 5.5 Codes d'erreur
| Code | Sens |
|------|------|
| 401 `non_autorise` | clé API / jeton invalide |
| 404 `non_trouve` | formulaire / session inconnu |
| 422 `validation` | requête invalide |
| 429 `quota_depasse` | limite de débit |
| 503 `service_indisponible` | modèle / LLM injoignable |

---

## 6. Modèle de données

### 6.1 Entités du domaine (dataclasses pures)
- **FormField** : `name`, `label`, `type` (`FieldType`), `required`, `enum_values`, `description`.
- **FormDefinition** : `account_id`, `form_id` (slug), `titre`, `fields`, `langue?`, `version`,
  `statut` (draft/published). Propriété `required_fields`. Modèle **plat** (pas de groupes imbriqués).
- **Account** : `nom`, `email_contact` (unique), `langue`, `persona_prompt`, `voice_prompt`,
  `actif`, `allowed_origins` (CORS par compte).
- **ApiKey** : `account_id`, `key_prefix` (affichage), `key_hash` (SHA-256, **jamais en clair**),
  `label`, `actif`.
- **LiveSession** : `account_id`, `form_id`, `id` (UUID), `statut`, `expires_at`.
- **UsageRecord** : `account_id`, `endpoint`, `horodatage` (**métadonnée de facturation, pas de PHI**).
- **FieldValue** / **FormState** : résultat d'extraction `{valeur, confiance}` par champ (clés FR).

`FieldType` : `STRING`, `TEXT`, `DATE`, `INT`, `NUMBER`, `ENUM`, `BOOL`.
`Confidence` : `CONFIANT`, `INCERTAIN`, `MANQUANT`.

### 6.2 Tables (SQLAlchemy) & migrations
Tables : `accounts`, `api_keys`, `form_definitions`, `live_sessions`, `usage_records`.
- `api_keys.key_hash` unique ; `form_definitions` unique `(account_id, form_id, version)`.
- **Aucune colonne clinique** (test d'audit garde-fou).

Migrations Alembic (`backend/migrations/versions`) :
1. `41c43edd76dc` — schéma initial (5 tables + index + contraintes).
2. `70002aa1f713` — ajoute `accounts.allowed_origins` (JSON).

---

## 7. Configuration (variables d'environnement)

Source : `backend/app/infrastructure/config.py` (`Settings`, pydantic-settings, 12-factor).
Copier `.env.example` → `.env`. Voir aussi `backend/.env.example`.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://vtf:vtf@db:5432/voicetoform` | Base Postgres (asyncpg) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis |
| `SPEECH_AGENT` | `stub` | Agent vocal (voir §3.2) |
| `STT_BACKEND` | `stub` | Backend STT |
| `WHISPERLIVE_URL` | `ws://srv-team-ia:9300` | Serveur STT WhisperLive en ligne de l'équipe |
| `WHISPER_MODEL` | `small` | Modèle Whisper (`large-v3` si CPU costaud) |
| `STT_LANGUAGE` | `""` | Vide ⇒ langue du compte/formulaire |
| `AUDIO_INPUT_RATE` | `24000` | Taux du micro (converti en 16 kHz côté STT) |
| `TTS_BACKEND` | `stub` | `piper_http` (Docker) / `piper` (local) |
| `PIPER_URL` | `http://piper:5000` | Serveur Piper HTTP (backend `piper_http`) |
| `PIPER_VOICE` / `TTS_VOICE_PATH` | — | Chemin voix `.onnx` |
| `PIPER_BINARY` | `piper` | Exécutable Piper (backend `piper` local) |
| `AGENT_BACKEND` | `scripted` | `ollama` en prod |
| `EXTRACTOR_BACKEND` | `null` | `ollama` en prod |
| `OLLAMA_HOST` | `https://ollama.com` | Ollama Cloud (nécessite `OLLAMA_API_KEY`) |
| `OLLAMA_MODEL` | `gpt-oss:120b-cloud` | Modèle agent/extracteur par défaut |
| `LLM_AGENT_MODEL` / `LLM_EXTRACTOR_MODEL` | `""` | Modèles distincts (vide ⇒ `OLLAMA_MODEL`) |
| `JWT_SECRET` | **(obligatoire, ≥32)** | Signature des jetons |
| `ADMIN_EMAIL` | `admin@local` | Compte admin |
| `ADMIN_PASSWORD` / `ADMIN_PASSWORD_HASH` | — | Clair (dev) / argon2 (prod, prioritaire) |
| `ADMIN_ACCESS_TTL_MINUTES` / `ADMIN_REFRESH_TTL_DAYS` | `30` / `7` | Durées jetons admin |
| `RATE_LIMIT_PER_MINUTE` | `120` | Rate-limit par IP |
| `SPECULATIVE_TRIGGER` | `false` | Déclenchement spéculatif (VAD) |
| `BARGE_IN` | `true` | Interruption de l'agent |
| `BACKCHANNEL` / `BACKCHANNEL_TEXT` | `false` / `D'accord…` | Accusé immédiat |
| `AGENT_MAX_TOKENS` | `1024` | Budget de génération de l'agent |
| `TTS_SENTENCE_CHUNKING` | `true` | Synthèse par phrase |
| `PROMPT_CACHE` | `true` | Cache du préfixe de prompt |
| `DEFAULT_LANGUAGE` | `fr` | Langue par défaut |
| `CORS_ORIGINS` | `[]` | Origines autorisées (JSON) |
| `SESSION_TOKEN_TTL_SECONDS` | `60` | Durée du jeton éphémère |
| `RESULT_RETENTION_SECONDS` | `600` | Rétention du formulaire final (PHI) |
| `MAX_USER_TURNS` | `12` | Garde-fou anti-boucle |

---

## 8. Sécurité

- **Deux JWT distincts** : jeton **admin** (access/refresh, `require_admin`) ≠ jeton **éphémère**
  de session live (`aud`=session, `jti` anti-rejeu, TTL court). `JWT_SECRET` ≥ 32 (validator).
- **Clés API** : hachées **SHA-256 en base** (jamais en clair) ; affichées une seule fois à la
  création. Rotation/révocation scopées par compte.
- **Mots de passe admin** : hachés **argon2** ; `ADMIN_PASSWORD_HASH` prioritaire en prod.
- **CORS par compte** (`Account.allowed_origins`) + global `CORS_ORIGINS`. WS : contrôle d'`Origin`
  (fermeture `4403`).
- **Rate-limiting** par IP + **en-têtes de sécurité** (CSP, HSTS, nosniff, Referrer-Policy) via
  middlewares. `/health` exempté.
- **Anti-rejeu** du jeton live via `jti` (usage unique). ⚠️ Le garde de rejeu et le result store
  sont **en mémoire** : un déploiement multi-worker nécessite un backend Redis partagé.

---

## 9. Données de santé — conformité

- **Aucune persistance** d'audio ni de transcript. La base ne stocke que des **métadonnées**
  (comptes, clés, formulaires, usage).
- Le **formulaire final** est gardé en mémoire à TTL court (`RESULT_RETENTION_SECONDS`) puis purgé.
- **Piper (TTS) auto-hébergé.** ⚠️ **Ollama Cloud** (agent + extraction) est un **service tiers** :
  le transcript envoyé pour l'extraction transite par `ollama.com`. À arbitrer pour les données de
  santé (revenir à un Ollama auto-hébergé si aucun envoi tiers n'est acceptable).
- **Logs JSON sans contenu clinique** ; `/metrics` = agrégats uniquement (test d'audit garde-fou).

---

## 10. Observabilité

- `GET /metrics` : `InMemoryMetrics` — compteurs (`ws_connections`, `sessions_completed/incomplete`,
  `user_turns`) et latences (`form_state_latency_ms`). Aucun PHI.
- Logs structurés JSON initialisés au démarrage (`lifespan`).
- Usage facturable : un `UsageRecord` est écrit à la création de session
  (`GET /admin/api/accounts/{id}/usage`).

---

## 11. Tests

- Suite backend : `cd backend && .venv/Scripts/python.exe -m pytest` (mocks STT/TTS/LLM ;
  les tests `integration` nécessitant des services réels sont **skippés par défaut**).
- Couverture : clean-archi (garde-fou AST), sécurité/jetons, admin CRUD, form builder,
  orchestrateur live, extraction, segmenteur, adapters STT/TTS.
- Front : `cd frontend && npm run build` (tsc + vite).

---

## 12. Arborescence du dépôt

```
voice-to-form/
├─ backend/                 # API FastAPI (clean architecture)
│  ├─ app/{domain,application,infrastructure,interface}
│  ├─ migrations/           # Alembic (2 révisions)
│  ├─ scripts/              # hash_password.py, seed_dev.py, lock_deps.py
│  ├─ tests/                # pytest
│  └─ Dockerfile
├─ frontend/                # Admin React + TS (Vite) → nginx  (Dockerfile)
├─ piper-server/            # TTS Piper (HTTP)                 (Dockerfile)
├─ sdk/                     # SDK Python + TypeScript + doc intégration
├─ infra/Caddyfile          # reverse-proxy TLS (prod)
├─ voices/                  # voix Piper .onnx (montée en volume)
├─ docker-compose.yml       # profils dev / voice / prod
├─ .env.example             # configuration (copier en .env)
├─ ARCHITECTURE.md · RUNBOOK.md · BACKLOG.md · README.md · DOCUMENTATION_TECHNIQUE.md
└─ app/                     # ⚠️ v1 turn-based (archive, non déployé)
```

> Le dossier racine **`app/`** est l'ancien pipeline v1 (turn-based Whisper→LLM→Piper) conservé
> pour archive. Le service déployé est **`backend/app/`**. Ne pas les confondre.
