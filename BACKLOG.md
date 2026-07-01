# Backlog — Voice-to-Form **Live Sandwich** (v3)

> **Architecture : sandwich temps réel** (STT streaming → agent + extracteur → TTS), pas de speech-to-speech.
> Choix dicté par le **français** : un modèle S2S anglais-only (PersonaPlex) ne convenait pas.
> Le sandwich permet le FR de bout en bout tout en gardant une **conversation live**.
>
> Le v2 (PersonaPlex / S2S) est archivé dans `docs/BACKLOG_v2_personaplex_archive.md`.
> Transport et pattern de streaming **inspirés de la doc LangChain voice-agent** (RunnableGenerator,
> producteur-consommateur async, mémoire par thread_id).

---

## Architecture cible

```
                         WebSocket (audio Opus/PCM, full-duplex applicatif)
   Client ──audio────────▶┌──────────────────────────────────────────────┐
                          │  STT live : WhisperLive (faster-whisper       │
                          │  large-v3, langue=fr, hotwords médicaux)      │
                          │     │ transcripts partiels + finaux + conf/mot │
                          │     ├───────────────┬──────────────────────────┤
                          │     ▼               ▼                          │
                          │  AGENT (LLM rapide)   EXTRACTEUR (LLM précis)  │
                          │  mène le dialogue,    lit le transcript,        │
                          │  relance, confirme    remplit form_state JSON   │
                          │     │ texte réponse        │ {valeur, confiance} │
                          │     ▼                       ▼ (→ client)        │
                          │  TTS : Piper (voix FR, local)                  │
   Client ◀──audio────────└──────────────────────────────────────────────┘
```

### Pourquoi deux LLM (clean separation)
- **Agent** = conversation : décide quoi demander, relance sur un champ manquant, confirme, clôt. Optimisé **latence** (petit modèle rapide).
- **Extracteur** = structuration : lit le transcript en continu, produit le formulaire validé Pydantic avec confiance par champ. Optimisé **précision** (modèle plus capable, appels debounced).
- Les deux dérivent d'une **seule `FormDefinition`** (DRY) : un `prompt_builder` génère et les instructions de l'agent et le schéma d'extraction.

---

## Nature & décisions actées

- **Service B2B**, hébergé séparément, **consommé par les backends clients** via API ; le front client ouvre le WS avec un **jeton éphémère** (clé API jamais exposée au navigateur).
- **STT :** WhisperLive (faster-whisper **large-v3**), `language=fr`, **hotwords** = lexique médical, scores de confiance par mot exploités.
- **Agent LLM :** modèle rapide (latence) ; **Extracteur LLM :** modèle précis (sortie structurée). Tous deux via un port, fournisseur configurable (Ollama Cloud ou autre).
- **TTS :** Piper local, voix FR (gratuit, rapide). *Pas de streaming token-audio : on synthétise par phrase/segment court.*
- **Transport :** WebSocket full-duplex applicatif, pipeline async par événements (inspiré doc LangChain).
- **Multi-langue :** `langue ∈ {en, fr}` portée par **compte** (surchargeable par formulaire) ; FR prioritaire.
- **Front :** React + TS (Vite) pour le portail Admin. **Back :** FastAPI async. **DB :** PostgreSQL. **Cache/sessions :** Redis. **Orchestration :** docker-compose (profils dev/prod).
- **Clés API en base** (hachées). Formulaires **dynamiques par compte**.
- **Dev sans GPU :** WhisperLive tourne en CPU (modèle `small`/`base` en dev) ou via **stub STT** ; large-v3 GPU en prod.

### Stack figée
FastAPI · SQLAlchemy 2.0 async · Alembic · PostgreSQL 16 · Redis 7 · WhisperLive (faster-whisper) ·
Piper · 2× LLM (agent/extracteur) · React + TS + Vite · Caddy (TLS) · Docker Compose.

---

## Conventions de travail

- **Clean Architecture** : `domain` ← `application (ports)` ← `infrastructure (adapters)` ← `interface`. Dépendances vers l'intérieur uniquement.
- **SOLID / DRY** : un cas d'usage = une classe ; chaque dépendance externe (STT, TTS, LLM, repos) derrière un **port** (Protocol) ; persona + schéma d'extraction dérivés d'une seule `FormDefinition`.
- **Python 3.11+**, type hints, docstrings FR, `ruff` + `black`.
- **Secrets** via `.env` / docker secrets (`pydantic-settings`), jamais en dur.
- **Sécurité d'abord** : clés hachées, jetons courts, TLS, non-persistance des données de santé.
- **Tests** : chaque ticket backend livre ≥ 1 test `pytest` vert. STT/TTS/LLM **mockés** via leur port ; appels réels en tests `integration` (skippés sans GPU/clé).
- **API versionnée** (`/v1`), erreurs homogènes `{erreur, detail}`.
- **DoD** : tourne en profil `dev`, tests verts, ticket documenté, **bout-en-bout testable dès l'EPIC 7**.

---

## Arborescence cible

```
voice-to-form/
├── docker-compose.yml           # profils dev (stt CPU/stub) / prod (GPU)
├── ARCHITECTURE.md
├── .env.example
├── infra/Caddyfile
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── app/
│       ├── domain/              # entities, value_objects, errors
│       ├── application/         # ports/ + cas d'usage (accounts, forms, integration, live)
│       ├── infrastructure/      # db, stt (whisperlive+stub), tts (piper), llm (agent/extracteur), security, cache
│       └── interface/           # api/ (admin, integration), ws/ (live), deps, main
├── stt-server/                  # WhisperLive (conteneur) + config FR/hotwords
├── frontend/                    # React + TS + Vite (portail Admin + console test live)
│   └── src/{api,components,pages,features}
└── sdk/                         # SDK client (TS + Python) + exemples d'intégration
```

---

## Carte des EPICs

| EPIC | Thème | Dépend de |
|------|-------|-----------|
| 0 | Socle & Clean Architecture + docker-compose | — |
| 1 | Domaine & persistance (Postgres, clés en DB, formulaires) | 0 |
| 2 | Sécurité & Auth Admin | 1 |
| 3 | Admin : comptes, clés API, langue, persona | 2 |
| 4 | Constructeur de formulaires dynamiques + dérivation DRY | 3 |
| 5 | API d'intégration cliente (jeton éphémère) + SDK + doc | 3 |
| 6 | Briques voix : STT (WhisperLive) · TTS (Piper) · LLM agent+extracteur | 0 |
| 7 | Orchestration live WebSocket (pipeline async sandwich) | 5, 6 |
| 8 | Extraction structurée temps réel (form_state) | 4, 7 |
| 9 | Frontend React Admin (+ console de test live) | 3, 4, 7 |
| 10 | Sécurité santé, conformité & observabilité | 7, 8 |
| 11 | Déploiement, GPU prod & DX (< 30 min) | tous |

> **Chemin critique vers une démo live :** 0 → 1 → 6 → 5 → 7 → 8 (STT en CPU/stub, sans GPU).

---

# EPIC 0 — Socle & Clean Architecture

### CORE-0.1 — Squelette Clean Architecture
**But :** poser les 4 couches + règle de dépendance.
**Tâches :** créer `domain/`, `application/ports`, `infrastructure/`, `interface/` ; `main.py` FastAPI + `GET /health` ; `deps.py` (composition root) ; lint/format/CI.
**Acceptation :** `/health` → 200 ; test vérifie que `domain` n'importe ni FastAPI ni SQLAlchemy.
**Test :** `test_health`, `test_dependency_rule`.

### CORE-0.2 — Configuration 12-factor
**Tâches :** `infrastructure/config.py` (pydantic-settings) : `database_url`, `redis_url`, `stt_backend` (whisperlive|stub), `whisperlive_url`, `whisper_model`, `stt_language`, `tts_voice_path`, `llm_agent_*`, `llm_extractor_*`, `jwt_secret`, `admin_*`, `default_language`, `cors_origins`. `.env.example` complet.
**Acceptation :** secret manquant → erreur claire au boot.

### CORE-0.3 — docker-compose dev/prod
**Tâches :** services `backend, frontend, db, redis, stt-server (WhisperLive), proxy` ; profils `dev` (STT CPU `small`/stub) / `prod` (STT GPU `large-v3`) ; healthchecks ; service `migrate` one-shot.
**Acceptation :** `docker compose --profile dev up` démarre back+front+db+redis+stt ; `/health` vert.

---

# EPIC 1 — Domaine & persistance

### DATA-1.1 — Entités & value objects
**Tâches :** `Account` (nom, email, **langue**, persona, actif), `ApiKey` (hachée), `FormDefinition` (slug, version, langue?, titre, statut), `FormField` (name, label, type, required, enum_values, description), `LiveSession`, `FormState`, `UsageRecord`. VO : `Language(en|fr)`, `Confidence`, `FieldType`. Aucune dépendance infra.
**Acceptation :** invariants validés (enum sans valeurs → erreur domaine).

### DATA-1.2 — Ports de repository
**Tâches :** Protocols `AccountRepo, ApiKeyRepo, FormRepo, SessionRepo, UsageRepo` (async, typés) + fake in-memory pour tests.

### DATA-1.3 — PostgreSQL + SQLAlchemy 2.0 async + Alembic
**Tâches :** modèles `db/models.py`, impl repos, migration initiale, `migrate` dans compose.
**Acceptation :** `alembic upgrade head` crée le schéma ; CRUD compte OK.
**Test :** repos contre Postgres de test (parité avec le fake).

### DATA-1.4 — Clés API en base (hachées)
**Tâches :** génération `token_urlsafe`, hachage (préfixe indexé + hash), affichage clair 1×, vérification, révocation, rotation (N clés actives).
**Acceptation :** clé révoquée refusée ; rotation sans coupure.

---

# EPIC 2 — Sécurité & Auth Admin

### SEC-2.1 — Auth admin
**Tâches :** mot de passe **argon2** ; session **JWT** (access court + refresh) ; `require_admin`.
**Acceptation :** mauvais mdp → 401 ; session expirée → 401.

### SEC-2.2 — Garde-fous edge
**Tâches :** rate-limit (Redis) par IP/clé ; CORS par compte ; en-têtes sécurité (HSTS, CSP) ; erreurs homogènes (400/401/403/404/409/422/429/503).
**Acceptation :** quota dépassé → 429 ; origine non autorisée bloquée.

---

# EPIC 3 — Admin : comptes, clés, langue, persona

### ADM-3.1 — CRUD comptes + langue par compte
**Tâches :** `CreateAccount/UpdateAccount/SetLanguage/Deactivate` ; route `/admin/api/comptes` ; `langue ∈ {en, fr}`.
**Acceptation :** créer compte FR et EN ; la langue conditionne STT (WhisperLive `fr`), persona agent et TTS.

### ADM-3.2 — Gestion des clés API (UI + REST)
**Tâches :** générer/lister(masquées)/révoquer ; clair 1× ; multi-clés.
**Acceptation :** rotation/révocation immédiates sur `/v1`.

### ADM-3.3 — Persona de l'agent par compte
**Tâches :** text-prompt persona (rôle/ton de l'agent conversationnel), cohérent avec la langue. (Pas de voice-prompt : la voix vient de Piper, choix de voix FR par compte.)
**Acceptation :** un compte FR « assistant clinique » et un EN « front-desk » produisent des dialogues distincts.

---

# EPIC 4 — Constructeur de formulaires dynamiques

### FORM-4.1 — Modèle de formulaire dynamique
**Tâches :** `FormDefinition` + `FormField` persistés ; types (`string,text,date,int,enum,bool`) ; `required`, `enum_values`, `description`, langue optionnelle (override compte) ; versionnage + statut draft/published.
**Acceptation :** créer « consultation » FR et « rapport_chirurgie » FR pour deux comptes ; isolation par compte.
**Test :** CRUD + validation (enum sans valeurs rejeté).

### FORM-4.2 — Dérivation persona + schéma d'extraction (DRY)
**Tâches :** `prompt_builder` unique produisant depuis une `FormDefinition` : (a) **instructions agent** (« demande les champs requis manquants, en langue X, un à la fois ») et (b) **schéma d'extraction plat** (champ → type interne) pour l'extracteur. Inclut la liste de **hotwords** (labels/jargon) transmise à WhisperLive.
**Acceptation :** modifier un champ change agent, schéma ET hotwords sans double saisie.
**Test :** un formulaire → trois sorties cohérentes.

### FORM-4.3 — Endpoints de découverte
**Tâches :** `GET /v1/integration/forms` + `GET /v1/integration/forms/{form_id}` (JSON Schema), **scopés au compte**.
**Acceptation :** 200 correct ; 404 si inconnu.

---

# EPIC 5 — API d'intégration cliente (jeton éphémère) + SDK

### INT-5.1 — Démarrage de session live (server-to-server)
**Tâches :** `POST /v1/integration/sessions` (`X-API-Key`, body `{form_id}`) → crée `LiveSession`, **mint JWT éphémère** (TTL ~60 s, `aud=session_id`, usage unique) → `{session_id, ws_url, token, language, form_schema, expires_at}`. Port `EphemeralTokenPort`.
**Acceptation :** token valide ouvre le WS ; expiré/rejoué refusé.

### INT-5.2 — Récupération du résultat
**Tâches :** `GET /v1/integration/sessions/{id}/result` (server-to-server) → formulaire final + statut. Rétention courte, **sans audio**.
**Acceptation :** backend client récupère le formulaire ; 404 si expiré.

### INT-5.3 — SDK client + doc (< 30 min)
**Tâches :** `sdk/` : SDK serveur (TS + Python : `createSession`, `getResult`) + helper frontend (ouverture WS, capture micro PCM, réception `form_state`/audio/transcript). README « intégrer en 4 appels » + exemple end-to-end.
**Acceptation :** suivre le README intègre une app démo de bout en bout.

---

# EPIC 6 — Briques voix (STT · TTS · LLM)

> **État :** socle v3 **livré** — ports `SttStreamPort`/`TtsPort` (`application/ports/{stt,tts}.py`),
> adapters **stub** (STT/TTS) + **WhisperLive** + **Piper**, composition **sandwich**
> (`infrastructure/speech/sandwich.py`) branchée sur l'orchestrateur via `SpeechAgentPort`
> (`SPEECH_AGENT=sandwich`). Config migrée v2→v3 (additive, rétro-compatible). **Hotwords du
> formulaire → STT livrés** (FORM-4.2 : `build_hotwords` dérive labels+enum de la `FormDefinition`,
> passés par session via `SpeechAgentPort.open(..., hotwords=)` → WhisperLive). Restent à finaliser :
> réglage VAD réel, et validation `integration` GPU.

### VOX-6.1 — Port `SttStreamPort` + adapter WhisperLive
**But :** STT streaming abstrait, implémenté par WhisperLive.
**Tâches :** port `open(language, hotwords)`, `send_audio(frame)`, `receive() -> {partial|final|endpoint, text, stable?, words[conf]}`, `close()`. Adapter client WebSocket vers le serveur WhisperLive (`stt-server`), mapping des segments (partiels/finaux + `probability` par mot). Config `language=fr`, `hotwords` du formulaire. **Latence (LIVE-7.4) :** activer le **VAD/endpointing** (`vad_silence_ms`, `vad_min_chunk_ms`) et émettre un événement **`endpoint`** (fin de parole) + un drapeau **`stable`** sur les partiels fiables (`partial_confidence_min`), distincts du final. **Garder `large-v3`** (précision médicale, pas de turbo/distil).
**Acceptation :** un flux audio FR produit partiels (dont stables) + un `endpoint` puis le final, avec confiances.
**Test :** `integration` contre WhisperLive (skippé sans serveur) ; unit avec faux flux.

### VOX-6.2 — Stub STT (dev sans GPU)
**Tâches :** `infrastructure/stt/stub.py` : transcripts **scriptés** déterministes (scénario), même interface que le port.
**Acceptation :** pipeline live complet tourne en `dev` avec le stub.
**Test :** scénario « champ manquant → question → réponse → complété ».

### VOX-6.3 — Port `TtsPort` + adapter Piper
**Tâches :** `synthetiser(texte, voix) -> bytes WAV` ; voix FR chargée **une fois** (warm). **TTS pipeliné (LIVE-7.4) :** synthèse **par phrase**, alimentée par le segmenteur (`application/live/segmenter.py`) via une **file** — on joue la 1ʳᵉ phrase pendant que l'agent génère la suite (`tts_sentence_chunking`).
**Acceptation :** `synthetiser("bonjour")` → WAV FR non vide ; un texte multi-phrases produit le **1er son avant** la fin de génération (cible time-to-first-audio §5).
**Test :** en-tête RIFF/WAVE ; segmenteur → phrases (cf. `test_segmenter`).

### VOX-6.4 — Port `LlmPort` + clients agent & extracteur
**Tâches :** `get_agent_llm()` (rapide) et `get_extractor_llm()` (précis) ; fournisseur configurable (Ollama Cloud par défaut). `with_structured_output` pour l'extracteur. **Latence (LIVE-7.4) :** `repondre` en **streaming** (`AsyncIterator[str]`) pour alimenter le segmenteur ; **`max_tokens` borné** (`agent_max_tokens`, agent concis) ; **prompt caching** du préfixe stable (système + schéma) quand le fournisseur le supporte (`prompt_cache`).
**Acceptation :** agent répond court et **en flux** ; extracteur renvoie une structure valide.
**Test :** `integration` skippé sans clé ; unit mockés.

---

# EPIC 7 — Orchestration live WebSocket (pipeline sandwich)

### LIVE-7.1 — Endpoint WS authentifié
**Tâches :** `interface/ws/live.py` : `GET /v1/live/{session_id}` (WebSocket) ; valide **jeton éphémère** + `Origin` ; charge compte/persona/langue/form_def/hotwords.
**Acceptation :** sans jeton valide → fermeture 4401 ; sinon session ouverte.

### LIVE-7.2 — Pipeline async sandwich (cas d'usage `RunLiveDialogue`)
**Tâches :** pont bidirectionnel inspiré de la doc LangChain :
- audio client → `SttStreamPort` ;
- sur **transcript final** → **agent** (réponse, streamée) → `TtsPort` → audio au client ;
- transcript (partiel+final) → **extracteur** (debounced) → `form_state` au client ;
- messages de contrôle (`transcript`, `form_state`, `agent_text`, `backchannel`, `interrupted`, `final`, `error`) ; **chevauchement** (extraction + STT final pendant que l'agent parle) ; **annulation** propre sur barge-in ; backpressure et latence maîtrisées.
**Acceptation :** on parle, l'agent répond en voix FR, le `form_state` se met à jour ; pas de coupure ; une reprise de parole coupe l'agent.
**Test :** intégration avec stub STT + LLM mockés (cf. `test_orchestrator`, `test_orchestrator_latency`).

### LIVE-7.3 — État de session & cycle de vie
**Tâches :** registre sessions (Redis) pour TTL/jetons/multi-worker ; **warm-up modèles au `lifespan`** + connexions WhisperLive/Piper persistantes (latence) ; fermeture propre (timeout, déconnexion, complétion).
**Acceptation :** session expirée/déconnectée nettoyée ; pas de fuite de connexions ; 1er tour non pénalisé par un cold start.

### LIVE-7.4 — Optimisations de latence *(transverse, cf. ARCHITECTURE §5)*
**But :** ramener le tour ressenti de ~3–5 s à **~1,5–2,5 s** (réel + perçu), via des primitives infra-indépendantes.
**Tâches :**
- **Déclenchement spéculatif :** sur `endpoint` (VAD) + meilleur **partiel stable**, lancer agent + extracteur sans attendre le final ; le final **ré-extrait** (fusion idempotente). Réglages `speculative_trigger`, `vad_silence_ms`, `partial_confidence_min`.
- **Segmenteur de phrases → TTS pipeliné** (`application/live/segmenter.py`) : `iter_sentences`/`aiter_sentences` entre le streaming agent et la file TTS.
- **Backchannel** (`backchannel`, `backchannel_text`) : accusé immédiat à l'`endpoint`.
- **Barge-in** (`application/live/turn_control.py`, `barge_in`) : annulation propre de la sortie agent+TTS sur reprise de parole.
- **Métriques par étape** : `endpoint_to_first_audio_ms`, `backchannel_latency_ms` (cf. `LIVE_LATENCY_METRICS`, OBS-10.2).
**Acceptation :** scénario stub « endpoint → backchannel → réponse par phrases → barge-in annule » ; cibles §5 instrumentées.
**Test :** `test_segmenter`, `test_turn_control`, `test_speech_events`, `test_orchestrator_latency` (verts).
**Note :** les primitives sont déjà livrées et branchées sur l'orchestrateur ; les adapters STT WhisperLive (`endpoint`/`stable`) et TTS Piper (file par phrase) finalisent le levier à l'EPIC 6.

---

# EPIC 8 — Extraction structurée temps réel

### EXTR-8.1 — Port `FormExtractorPort` + impl LLM
**Tâches :** `update(transcript, form_def, partiel) -> FormState` ; sortie structurée plate dérivée du `prompt_builder` ; reconstruction `{valeur, confiance}` ; **fusion** sans écraser le confiant. Exploiter les confiances par mot de WhisperLive comme signal.
**Acceptation :** sur transcript d'exemple, formulaire valide ; complétion progressive correcte.
**Test :** structure + fusion (LLM mocké).

### EXTR-8.2 — Boucle incrémentale & fin de session
**Tâches :** extraction **debounced** ; émission `form_state` au client ; détection « tous requis confiants » → signal de clôture à l'agent ; garde-fou anti-boucle (abandon d'un champ après N relances) ; **coordination agent↔extracteur** (l'agent relance sur les champs que l'extracteur signale manquants).
**Acceptation :** `form_state` < 1–2 s après énoncé ; session conclut quand requis complets.
**Test :** scénario multi-tours complet (stub + extracteur mocké).

---

# EPIC 9 — Frontend React Admin

### UI-9.1 — Socle React + TS + Vite + auth
**Tâches :** projet Vite TS, client API typé, routage, login (JWT), garde de routes.
**Acceptation :** login → dashboard ; 401 redirige.

### UI-9.2 — Comptes, clés, langue, persona
**Tâches :** CRUD comptes (sélecteur langue en/fr), gestion clés (1×, révocation), édition persona + choix voix FR Piper.
**Acceptation :** login → créer compte FR → générer clé → configurer persona.

### UI-9.3 — Constructeur de formulaires
**Tâches :** form builder (type, requis, enum, description, langue, hotwords) ; brouillon/publication ; aperçu schéma.
**Acceptation :** créer et publier un formulaire pour un compte.

### UI-9.4 — Tableau de bord usage + **console de test live**
**Tâches :** métriques par compte ; **console** qui ouvre une vraie session live (micro → WS), affiche transcript (partiel/final), `form_state` en direct et joue l'audio de l'agent.
**Acceptation :** lancer une session de test, voir le formulaire se remplir et entendre l'agent.

---

# EPIC 10 — Sécurité santé, conformité & observabilité

### OBS-10.1 — Non-persistance des données de santé
**Tâches :** audio + transcript **non persistés** par défaut (mémoire) ; option chiffrée + TTL court + opt-in ; logs **sans** contenu clinique (attention au log level de WhisperLive qui peut écrire le transcript).
**Acceptation :** audit : aucune donnée clinique en base/logs.

### OBS-10.2 — Observabilité & latence
**Tâches :** logs structurés (corrélation `session_id`), métriques (connexion WS, latence STT partiel/final, **`endpoint_to_first_audio_ms`**, **`backchannel_latency_ms`**, délai `form_state`, compteur `barge_in`, taux d'abandon de champ). Référence des noms : `LIVE_LATENCY_METRICS` (`observability/metrics.py`). **Garde-fou de non-régression** : alerter si une métrique dépasse durablement la cible §5.
**Acceptation :** dashboard latence reflète les cibles d'`ARCHITECTURE.md §5` (réel + perçu).

---

# EPIC 11 — Déploiement, GPU prod & DX

### DEP-11.1 — Profil prod + GPU
**Tâches :** `stt-server` WhisperLive en **large-v3 GPU** (réservation GPU) ; `proxy` Caddy (TLS, validation Origin WS) ; secrets prod.
**Acceptation :** `docker compose --profile prod up` sert en TLS, STT GPU large-v3.

### DEP-11.2 — Runbook & DX
**Tâches :** README exploitation (dev CPU/stub vs prod GPU), migration, sauvegarde DB, rotation secrets, checklist d'intégration cliente.
**Acceptation :** intégrateur opérationnel en < 30 min.

---

## Ordre de développement conseillé

1. **EPIC 0–1** — socle clean arch + Postgres + clés en DB.
2. **EPIC 6** — briques voix + **stub STT** (débloque le live sans GPU).
3. **EPIC 5** — API d'intégration (jeton éphémère).
4. **EPIC 7–8** — pipeline live sandwich + extraction (le produit prend vie, avec stub).
5. **EPIC 2–4** — sécurité, admin, formulaires dynamiques.
6. **EPIC 9** — frontend Admin (+ console de test live).
7. **EPIC 10–11** — conformité, observabilité, déploiement GPU.

> Le flux live est testable de bout en bout dès l'EPIC 7 **avec le stub STT** (aucun GPU).
> Bascule prod = `STT_BACKEND=whisperlive` + WhisperLive large-v3 GPU (EPIC 11.1).

---

## Décisions clés (contexte pour Claude Code)

- **Sandwich, pas S2S** : le français impose STT/TTS séparés ; PersonaPlex (S2S) écarté car anglais-only.
- **STT = WhisperLive** (faster-whisper large-v3) : streaming WebSocket, `language=fr`, **hotwords médicaux**, confiance par mot. Tourne CPU en dev, GPU en prod.
- **Deux LLM** : agent (rapide, dialogue) + extracteur (précis, JSON structuré), dérivés d'une seule `FormDefinition`.
- **TTS = Piper** local FR (synthèse par phrase, pas de streaming token-audio).
- **Latence (LIVE-7.4)** : déclenchement **spéculatif** (VAD endpoint + partiel stable), **TTS pipeliné** par phrase, **backchannel**, **barge-in**, prompt caching + warm. Cible **tour ressenti ~1,5–2,5 s** (cf. ARCHITECTURE §5). STT gardé `large-v3` (précision médicale > vitesse).
- **Transport & pattern** inspirés de la doc LangChain voice-agent (pipeline async par événements, mémoire par thread_id).

## Données de santé — règle absolue
Base et portail Admin ne traitent **que des métadonnées** (comptes, clés, formulaires, compteurs).
**Jamais** d'audio ni de transcript clinique persistés. Cf. EPIC 10 (et log level WhisperLive).