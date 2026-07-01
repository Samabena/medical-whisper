# Backlog — Service API « Voice-to-Form » (remplissage médical par la voix)

> Fichier de référence pour le développement assisté par Claude Code.
>
> **Nature du projet :** service **autonome, hébergé séparément**, exposant une **API HTTP**.
> Les plateformes clientes (app médicale, etc.) l'appellent pour faire remplir leurs formulaires
> à partir d'une dictée vocale. **Pas d'interface utilisateur finale** de notre côté : les clients ont la leur.
>
> **Particularité clé — le dialogue de clarification :** si la dictée est ambiguë ou qu'il manque
> un champ obligatoire, le service ne rend pas un formulaire incomplet. Il **pose une question**
> (renvoyée en **audio**), garde la **session ouverte**, et attend la réponse (un **nouvel audio**)
> pour compléter. La boucle continue jusqu'à ce que le formulaire soit valide.
>
> **Stack figée :** FastAPI · faster-whisper (STT local) · Piper (TTS local) · Ollama Cloud `gpt-oss:120b` (LLM) · Pydantic (validation).

---

## Le flux complet (à garder en tête pour tous les tickets)

```
   ┌─ Client (plateforme tierce) ─────────────────────────────────────┐
   │  POST /sessions  { audio, form_id }                              │
   └──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        STT (faster-whisper) ── transcription
                              │
                              ▼
        Extraction (LLM → Pydantic) ── formulaire partiel + confiance/champ
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   Formulaire COMPLET & valide      Champ obligatoire manquant
              │                      ou information ambiguë
              ▼                               │
   Réponse : formulaire JSON                  ▼
   + statut "termine"            Génère une QUESTION de clarification
                                 → TTS (Piper) → audio
                                 → garde la session ouverte (état)
                                 → Réponse : { session_id, question_audio,
                                               question_texte, statut "clarification" }
                                              │
                                              ▼
                       Client rejoue l'audio au médecin, qui répond
                                              │
                                              ▼
                  POST /sessions/{session_id}/repondre  { audio }
                                              │
                                              ▼
                       STT → intègre la réponse → ré-évalue → boucle
```

---

## Conventions de travail (à respecter par Claude Code)

- **Langage :** Python 3.10+, type hints partout, docstrings en français.
- **Style :** `ruff` (lint) + `black` (format). Aucune variable inutilisée.
- **Secrets :** jamais en dur. Tout via `.env` lu par `pydantic-settings`.
- **API d'abord :** ce service est consommé par d'autres machines. Contrats d'API stables, versionnés (`/v1/...`), réponses d'erreur homogènes.
- **Structure :** code dans `app/`, tests dans `tests/`, un module par responsabilité.
- **Tests :** chaque ticket « backend » livre au moins un test `pytest` qui passe. STT/TTS/LLM mockés dans les tests unitaires ; vrais appels seulement dans les tests marqués `integration` (skippés sans clé/modèle).
- **Commits :** un commit par ticket, message préfixé par l'ID (ex. `[CORE-1] ...`).
- **DoD :** le code tourne, les tests passent, le ticket est documenté dans le README.

---

## Arborescence cible

```
voice-to-form/
├── .env.example
├── requirements.txt
├── README.md
├── BACKLOG.md                   # ce fichier
├── app/
│   ├── __init__.py
│   ├── main.py                  # app FastAPI + montage des routers (préfixe /v1)
│   ├── config.py                # réglages via pydantic-settings (.env)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── forms.py             # schémas Pydantic des formulaires médicaux
│   │   └── api.py               # modèles requête/réponse de l'API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stt.py               # transcription faster-whisper
│   │   ├── tts.py               # synthèse Piper (questions de clarification)
│   │   ├── llm.py               # client Ollama Cloud (partagé)
│   │   ├── extraction.py        # remplissage de formulaire (LLM → Pydantic)
│   │   └── clarification.py     # décide s'il faut une question + la formule
│   ├── sessions/
│   │   ├── __init__.py
│   │   └── store.py             # store de sessions avec état (formulaire partiel)
│   ├── routers/
│   │   └── sessions.py          # endpoints du flux (création + réponse + statut)
│   └── catalog/
│       └── forms_catalog.py     # catalogue des formulaires connus
└── tests/
    ├── test_health.py
    ├── test_forms_catalog.py
    ├── test_extraction.py
    ├── test_clarification.py
    └── test_session_flow.py
```

---

# EPIC 0 — Fondations
> **Skill epic :** `/implement-epic 0`

### INFRA-1 — Initialiser le service FastAPI
> **Skill :** `/implement-ticket INFRA-1` · `/verify-ticket INFRA-1`
**But :** squelette qui démarre, prêt pour une API versionnée.
**Tâches :**
- Créer l'arborescence (dossiers + `__init__.py`).
- `requirements.txt` : `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `python-dotenv`, `faster-whisper`, `piper-tts`, `langchain-ollama`, `python-multipart`, `pytest`, `httpx`.
- `app/main.py` : `FastAPI(title="Voice-to-Form API")`, routers montés sous `/v1`, endpoint `GET /health` → `{"status":"ok"}`.
**Acceptation :** `uvicorn app.main:app --reload` démarre ; `GET /health` répond 200.
**Test :** `tests/test_health.py`.

### INFRA-2 — Configuration centralisée (.env)
> **Skill :** `/implement-ticket INFRA-2` · `/verify-ticket INFRA-2`
**But :** réglages au même endroit, pas de secret en dur.
**Tâches :**
- `app/config.py` : `Settings(BaseSettings)` avec `ollama_api_key`, `ollama_model="gpt-oss:120b"`, `ollama_base_url="https://ollama.com"`, `whisper_model="medium"`, `whisper_device="auto"`, `piper_voice_path`, `session_ttl_minutes=30`.
- `.env.example` complet (secrets vides).
- `get_settings()` en singleton caché (`lru_cache`).
**Acceptation :** config lue depuis `.env` ; clé manquante → erreur claire au démarrage.
**Test :** instanciation de `Settings` avec un `.env` de test.

---

# EPIC 1 — Services partagés
> **Skill epic :** `/implement-epic 1`

### CORE-1 — Service STT (faster-whisper)
> **Skill :** `/implement-ticket CORE-1` · `/verify-ticket CORE-1`
**But :** audio → texte français.
**Tâches :**
- `app/services/stt.py` : modèle chargé une fois, `transcrire(chemin_audio: str) -> str`, `language="fr"`, `beam_size=5`, `compute_type="int8"`.
- Audio vide/illisible → chaîne vide (pas d'exception).
**Acceptation :** un .wav FR de test renvoie un texte non vide.
**Test :** transcription d'un échantillon dans `tests/fixtures/` (marqué `integration`).

### CORE-2 — Client LLM Ollama Cloud (partagé)
> **Skill :** `/implement-ticket CORE-2` · `/verify-ticket CORE-2`
**But :** accès unique au modèle, réutilisé par extraction ET clarification.
**Tâches :**
- `app/services/llm.py` : `ChatOllama` configuré (base_url + header `Authorization: Bearer` via `client_kwargs={"headers": {...}}`).
- `get_llm(temperature: float)`.
**Acceptation :** « dis bonjour » renvoie une réponse non vide avec clé valide.
**Test :** test `integration` skippé si `OLLAMA_API_KEY` absente.

### CORE-3 — Service TTS (Piper)
> **Skill :** `/implement-ticket CORE-3` · `/verify-ticket CORE-3`
**But :** texte de question → audio WAV, pour les clarifications.
**Tâches :**
- `app/services/tts.py` : voix chargée une fois, `synthetiser(texte: str) -> bytes` (WAV complet via `wave` + `synthesize_wav`).
- README : `python -m piper.download_voices fr_FR-siwis-medium --data-dir ...`.
**Acceptation :** `synthetiser("bonjour")` renvoie un WAV non vide (en-tête `RIFF`/`WAVE`).
**Test :** vérifie l'en-tête WAV des bytes.

---

# EPIC 2 — Catalogue de formulaires + schémas Pydantic
> **Skill epic :** `/implement-epic 2`

### FORM-1 — Schémas Pydantic des formulaires
> **Skill :** `/implement-ticket FORM-1` · `/verify-ticket FORM-1`
**But :** consultation, rapport de chirurgie, dossier médical en Pydantic (validation forte).
**Tâches :**
- `app/schemas/forms.py` : `Consultation`, `RapportChirurgie`, `DossierMedical`.
- Wrapper `Champ[T]` : `valeur: T | None` + `confiance: Literal["confiant","incertain","manquant"]`.
- Enums pour `saignement`, `type_anesthesie`. Champs obligatoires marqués ; défauts (`allergies="Aucune connue"`…).
**Acceptation :** valide un exemple correct, rejette un type invalide.
**Test :** instanciation de chaque modèle avec un exemple valide.

### FORM-2 — Catalogue + résolution
> **Skill :** `/implement-ticket FORM-2` · `/verify-ticket FORM-2`
**But :** retrouver le bon schéma depuis un `form_id`.
**Tâches :**
- `app/catalog/forms_catalog.py` : dict `form_id -> modèle` (`consultation_v1`, `rapport_chirurgie_v1`, `dossier_medical_v1`).
- `get_form_model(form_id)` ; erreur explicite si inconnu.
- Liste des champs obligatoires par formulaire (helper réutilisé par la clarification).
**Acceptation :** résolution des 3 ids + cas inconnu géré.
**Test :** `tests/test_forms_catalog.py`.

### FORM-3 — Endpoints de découverte des schémas
> **Skill :** `/implement-ticket FORM-3` · `/verify-ticket FORM-3`
**But :** le client peut connaître la structure d'un formulaire.
**Tâches :**
- `GET /v1/forms` : liste des `form_id`.
- `GET /v1/forms/{form_id}` : JSON Schema du modèle (`.model_json_schema()`).
**Acceptation :** 200 avec bon contenu ; 404 si inconnu.
**Test :** appel des deux routes via `httpx`.

---

# EPIC 3 — Extraction (remplissage validé)
> **Skill epic :** `/implement-epic 3`

### STW-1 — Service d'extraction (LLM → Pydantic validé)
> **Skill :** `/implement-ticket STW-1` · `/verify-ticket STW-1`
**But :** transcription + form_id → formulaire rempli, validé, avec confiance par champ.
**Tâches :**
- `app/services/extraction.py` : `extraire(transcription, form_id, formulaire_partiel=None) -> BaseModel`.
- Prompt strict : ne rien inventer, dates `AAAA-MM-JJ`, confiance par champ.
- **Sortie structurée** via `llm.with_structured_output(Modele)`.
- Si `formulaire_partiel` fourni (tour de clarification) : **compléter** sans écraser les champs déjà confiants.
- Échec de validation → 1 retry → erreur explicite.
**Acceptation :** sur une transcription d'exemple, instance Pydantic valide ; un 2e appel avec partiel complète sans tout réécrire.
**Test :** `tests/test_extraction.py` (LLM mocké) : structure correcte + fusion partiel/nouveau.

---

# EPIC 4 — Clarification (le cœur différenciant)
> **Skill epic :** `/implement-epic 4`

### CLAR-1 — Détecter ce qui doit être clarifié
> **Skill :** `/implement-ticket CLAR-1` · `/verify-ticket CLAR-1`
**But :** décider si le formulaire est complet ou s'il faut une question.
**Tâches :**
- `app/services/clarification.py` : `analyser(formulaire) -> list[ChampAClarifier]`.
- Règles : tout champ **obligatoire** marqué `manquant`, plus (optionnel) champs marqués `incertain`.
- Renvoie une liste priorisée (obligatoires d'abord).
**Acceptation :** un formulaire complet renvoie liste vide ; un incomplet liste les bons champs.
**Test :** cas complet / incomplet sur chaque formulaire.

### CLAR-2 — Formuler la question (texte) puis l'audio
> **Skill :** `/implement-ticket CLAR-2` · `/verify-ticket CLAR-2`
**But :** transformer « champ manquant » en question naturelle, lue par TTS.
**Tâches :**
- Générer une **question texte** courte et naturelle pour le(s) champ(s) à clarifier (via LLM ou gabarits par champ — commencer par gabarits, plus prévisible).
- Une question à la fois (le champ obligatoire prioritaire), pour un dialogue simple.
- Passer la question au TTS (CORE-3) → audio.
**Acceptation :** pour `date_intervention` manquante, question type « Quelle est la date de l'intervention ? » + audio non vide.
**Test :** `tests/test_clarification.py` : génération de la question (TTS mocké).

---

# EPIC 5 — Sessions avec état + endpoints du flux
> **Skill epic :** `/implement-epic 5`

### SESS-1 — Store de sessions
> **Skill :** `/implement-ticket SESS-1` · `/verify-ticket SESS-1`
**But :** mémoriser le formulaire partiel entre les tours.
**Tâches :**
- `app/sessions/store.py` : créer/lire/mettre à jour/supprimer une session.
- Contenu : `session_id`, `form_id`, `formulaire_partiel`, `champ_en_attente`, `statut`, horodatage.
- Expiration via `session_ttl_minutes` (nettoyage paresseux à l'accès).
- Implémentation **en mémoire** d'abord (dict), interface prête pour un backend Redis plus tard.
**Acceptation :** cycle create→get→update→delete OK ; session expirée non renvoyée.
**Test :** opérations du store + expiration (TTL simulé).

### SESS-2 — `POST /v1/sessions` (premier tour)
> **Skill :** `/implement-ticket SESS-2` · `/verify-ticket SESS-2`
**But :** démarrer le remplissage à partir d'un audio.
**Tâches :**
- Accepte `audio` (UploadFile) + `form_id` (ou détection auto par nom de fichier).
- Pipeline : sauver temp → STT → extraction → analyse clarification.
- Si complet → `{ statut:"termine", formulaire }` (pas de session conservée).
- Si incomplet → créer session, générer question (texte+audio) → `{ statut:"clarification", session_id, question_texte, question_audio (base64 ou stream), champs_restants }`.
- Nettoyer le fichier temp (`finally`).
**Acceptation :** dictée complète → `termine` ; dictée incomplète → `clarification` + session ouverte.
**Test :** `tests/test_session_flow.py` (STT/LLM/TTS mockés), les deux branches.

### SESS-3 — `POST /v1/sessions/{session_id}/repondre` (tours suivants)
> **Skill :** `/implement-ticket SESS-3` · `/verify-ticket SESS-3`
**But :** intégrer la réponse vocale du médecin et boucler.
**Tâches :**
- Accepte un nouvel `audio`, retrouve la session.
- STT → extraction en mode **complétion** (passe `formulaire_partiel`) → ré-analyse.
- Encore incomplet → nouvelle question (texte+audio), session mise à jour.
- Complet → `{ statut:"termine", formulaire }`, puis fermer la session.
- Session inconnue/expirée → 404 clair.
**Acceptation :** une réponse qui fournit le champ manquant termine la session ; sinon, nouvelle question.
**Test :** scénario multi-tours complet (mocké) : incomplet → réponse → terminé.

### SESS-4 — `GET /v1/sessions/{session_id}` (état)
> **Skill :** `/implement-ticket SESS-4` · `/verify-ticket SESS-4`
**But :** permettre au client d'inspecter l'état courant.
**Tâches :**
- Renvoie `statut`, `formulaire_partiel`, `champ_en_attente`, champs restants.
**Acceptation :** 200 avec l'état ; 404 si inconnue/expirée.
**Test :** lecture d'une session existante + cas absent.

---

# EPIC 6 — Robustesse & finitions
> **Skill epic :** `/implement-epic 6`

### OPS-1 — Gestion d'erreurs uniforme
> **Skill :** `/implement-ticket OPS-1` · `/verify-ticket OPS-1`
**But :** réponses d'erreur cohérentes, jamais de 500 nu.
**Tâches :**
- Handlers FastAPI : payload `{erreur, detail}` homogène.
- Codes : 400 (entrée invalide), 404 (form/session inconnue), 422 (validation), 503 (LLM indisponible).
**Acceptation :** chaque cas renvoie le bon code + message lisible.
**Test :** un test par code principal.

### OPS-2 — Warm-up des modèles au démarrage
> **Skill :** `/implement-ticket OPS-2` · `/verify-ticket OPS-2`
**But :** éviter la latence du 1er appel.
**Tâches :**
- `lifespan` FastAPI : précharger Whisper et la voix Piper au boot ; log « modèles chargés » + durée.
**Acceptation :** 1er appel réel sans attente de chargement.
**Test :** services chargés après démarrage.

### OPS-3 — Authentification des clients (clé API)
> **Skill :** `/implement-ticket OPS-3` · `/verify-ticket OPS-3`
**But :** seul un client autorisé peut appeler le service (il est hébergé séparément et exposé).
**Tâches :**
- Middleware/dépendance vérifiant un header `X-API-Key` contre une liste de clés en config.
- Endpoints `/v1/*` protégés ; `/health` public.
**Acceptation :** appel sans clé → 401 ; avec clé valide → 200.
**Test :** accès refusé/autorisé.

### OPS-4 — README + exemples d'intégration
> **Skill :** `/implement-ticket OPS-4` · `/verify-ticket OPS-4`
**But :** un client intègre le service en < 30 min.
**Tâches :**
- Install (venv, requirements, voix Piper, `.env`), lancement.
- **Documentation du flux** côté client : séquence d'appels `POST /sessions` → (boucle) `POST /sessions/{id}/repondre` → formulaire final, avec exemples `curl`.
- Format des réponses (statuts `termine` / `clarification`), gestion de l'audio renvoyé.
- Limites connues (latence STT/LLM par tour).
**Acceptation :** suivre le README permet d'intégrer le service de bout en bout.

---

# EPIC 7 — Portail d'administration clients (B2B) ✅
> **Skill epic :** `/implement-epic 7`

> Interface web pour les **plateformes clientes** (pas pour les médecins) : gérer leur accès,
> suivre leur consommation, consulter le catalogue de formulaires.
> Monté sous `/admin` (UI) et `/admin/api` (REST).

### ADMIN-1 — Modèle de compte client + persistance ✅
> **Skill :** `/implement-ticket ADMIN-1` · `/verify-ticket ADMIN-1`
**But :** représenter un client B2B et sa/ses clé(s) API.
**Tâches :**
- Modèle `ClientCompte` : `id`, `nom`, `email_contact`, `cles_api` (hashées), `actif`, `date_creation`.
- Persistance réelle (SQLite/Postgres via SQLAlchemy) — c'est le 1er besoin d'une vraie base.
- Migration depuis la liste de clés en config (OPS-3) vers la base.
**Acceptation :** créer/désactiver un compte ; une clé révoquée n'accède plus à `/v1`.
**Test :** CRUD compte + vérification qu'une clé hashée valide l'auth.

### ADMIN-2 — Gestion des clés API (création / rotation / révocation) ✅
> **Skill :** `/implement-ticket ADMIN-2` · `/verify-ticket ADMIN-2`
**But :** un client peut renouveler ses clés sans interruption.
**Tâches :**
- Endpoints `/admin/api` : générer une nouvelle clé, lister (masquées), révoquer.
- Supporter plusieurs clés actives par compte (rotation sans coupure).
- La clé n'est affichée en clair qu'une seule fois, à la création.
**Acceptation :** rotation possible avec deux clés valides en parallèle ; révocation immédiate.
**Test :** création + rotation + révocation.

### ADMIN-3 — Suivi de consommation ✅
> **Skill :** `/implement-ticket ADMIN-3` · `/verify-ticket ADMIN-3`
**But :** chaque client voit son usage (facturation, quotas).
**Tâches :**
- Compter par compte : nombre de sessions, de tours de clarification.
- Endpoint `GET /admin/api/usage` (filtrable par compte et période).
- Journalisation légère à chaque appel `/v1/sessions` via middleware (sans stocker l'audio ni les données de santé).
**Acceptation :** les compteurs reflètent l'usage réel d'un compte.
**Test :** simulation d'appels → compteurs corrects.

### ADMIN-4 — Interface web d'administration ✅
> **Skill :** `/implement-ticket ADMIN-4` · `/verify-ticket ADMIN-4`
**But :** portail self-service pour les clients (au-dessus des endpoints `/admin`).
**Tâches :**
- Pages : connexion (`/admin/connexion`), tableau de bord (`/admin/`), gestion des clés, catalogue de formulaires.
- UI sobre et fonctionnelle montée sous `/admin`.
- Authentification administrateur distincte de la clé API `/v1` (mot de passe `ADMIN_PASSWORD`).
**Acceptation :** un client se connecte, voit son usage, gère ses clés, parcourt les formulaires.
**Test :** parcours principal (login → dashboard → rotation de clé).

> ⚠️ **Données de santé :** le portail ne doit JAMAIS exposer le contenu des formulaires remplis
> ni l'audio. Il ne traite que des métadonnées (comptes, clés, compteurs d'usage).

---

## Avant de commencer — environnement local

> **Skill :** `/dev-setup` — configure venv, dépendances, `.env`, voix Piper, et vérifie `GET /health`.

---

## Ordre de développement conseillé

1. **EPIC 0** — squelette + config.
2. **EPIC 1** — STT, LLM, TTS (briques partagées).
3. **EPIC 2** — formulaires + catalogue.
4. **EPIC 3** — extraction validée.
5. **EPIC 4** — clarification (détection + question/audio).
6. **EPIC 5** — sessions avec état + endpoints du flux (le produit prend vie ici).
7. **EPIC 6** — robustesse, auth, doc.
8. **EPIC 7** — portail admin B2B (**plus tard**, quand il y a de vrais clients).

> Le flux complet n'est testable de bout en bout qu'à la fin de l'EPIC 5.
> Les EPICs 1→4 sont des briques ; garder les contrats d'API stables dès l'EPIC 5.

---

## Décisions de conception actées (contexte pour Claude Code)

- **Service B2B sans UI :** appelé par d'autres plateformes via HTTP. Pas de WebSocket ni de client navigateur côté serveur.
- **Dialogue de clarification avec état :** le serveur garde la session et le formulaire partiel entre les tours.
- **Questions renvoyées en audio (TTS Piper)** ; réponses du médecin reçues en audio (STT Whisper). Le texte accompagne toujours l'audio dans les réponses, pour le débogage et l'affichage côté client.
- **Une question à la fois** (champ obligatoire prioritaire) pour garder le dialogue simple et déterministe.
- **Store de sessions en mémoire pour commencer**, interface prête pour Redis (multi-instances) plus tard.

---

## Skills disponibles (commandes `/`)

> Fichiers dans `.claude/commands/` — utilisables directement dans Claude Code.

| Commande | Usage | Description |
|---|---|---|
| `/implement-ticket <ID>` | `/implement-ticket INFRA-1` | Implémente un ticket : tâches + tests + commit |
| `/verify-ticket <ID>` | `/verify-ticket CORE-2` | Vérifie les critères d'acceptation d'un ticket |
| `/implement-epic <N>` | `/implement-epic 0` | Implémente tous les tickets d'un epic dans l'ordre |
| `/dev-setup` | `/dev-setup` | Configure l'environnement local (venv, deps, .env, Piper) |
| `/run-tests [arg]` | `/run-tests unit` | Lance pytest (unit / integration / all / ticket-id) |

---

## Comment lancer un ticket avec Claude Code

```
/implement-ticket INFRA-1
```

Ou, pour enchaîner tout un epic d'un coup :

```
/implement-epic 0
```

Un ticket à la fois → tests verts → commit → suivant.
