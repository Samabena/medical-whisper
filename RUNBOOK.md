# Runbook d'exploitation — Voice-to-Form Live (sandwich CPU)

> Architecture : `ARCHITECTURE.md` · Doc technique : `DOCUMENTATION_TECHNIQUE.md`
> · Backlog : `BACKLOG.md` · Intégration cliente : `sdk/README.md`.

Architecture cible : **« sandwich »** — STT (WhisperLive en ligne) → agent + extracteur
(Ollama Cloud) → TTS (Piper). Services Docker locaux : `backend`, `frontend`, `db`, `redis`,
`piper`, `proxy` (+ `migrate` one-shot). Le STT et le LLM sont des services **externes**.

---

## 1. Démarrage local (dev, hors-ligne, sans modèle)

```bash
cp .env.example .env          # garder SPEECH_AGENT=stub, EXTRACTOR_BACKEND=null
#   → renseigner au minimum : POSTGRES_PASSWORD, JWT_SECRET (≥32), ADMIN_PASSWORD
docker compose --profile dev up --build
```
- Admin (React) : http://localhost:5173
- API / santé : http://localhost:8000/health · Swagger : http://localhost:8000/docs
- Le dialogue live tourne avec l'**agent stub** (scénario scripté) — aucun modèle, aucun GPU.

### Tester la vraie chaîne vocale en local
Ajouter le profil `voice` (démarre `piper` ; STT et LLM sont des services en ligne) puis basculer `.env` :
```ini
SPEECH_AGENT=sandwich
STT_BACKEND=whisperlive     ; WHISPERLIVE_URL=ws://srv-team-ia:9300
TTS_BACKEND=piper_http      ; PIPER_URL=http://piper:5000
AGENT_BACKEND=ollama
EXTRACTOR_BACKEND=ollama    ; OLLAMA_HOST=https://ollama.com ; OLLAMA_API_KEY=<clé>
```
```bash
docker compose --profile dev --profile voice up --build
```

### Sans Docker (itération backend)
```bash
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]"
pytest                              # suite de tests (mock STT/TTS/LLM)
alembic upgrade head                # nécessite DATABASE_URL accessible
uvicorn app.interface.main:app --reload
```
### Front en dev
```bash
cd frontend && npm install && npm run dev    # proxy vers backend :8000
```

---

## 2. Déploiement prod (CPU, sans GPU)

### Pré-requis
- Hôte Linux avec Docker + Docker Compose. **Pas de GPU nécessaire.** Charge locale légère
  (Piper CPU) : le STT (serveur en ligne) et le LLM (Ollama Cloud) tournent hors de cet hôte.
- DNS pointant vers l'hôte (pour le TLS auto Caddy).

### Configurer `.env` (prod)
```ini
DOMAIN=api.mondomaine.com
SPEECH_AGENT=sandwich

STT_BACKEND=whisperlive
WHISPERLIVE_URL=ws://srv-team-ia:9300   # serveur WhisperLive en ligne de l'équipe
WHISPER_MODEL=large-v3                  # transmis dans le handshake ; small si serveur limité

TTS_BACKEND=piper_http
PIPER_URL=http://piper:5000
PIPER_VOICE=/voices/fr_FR-siwis-medium.onnx

AGENT_BACKEND=ollama
EXTRACTOR_BACKEND=ollama
OLLAMA_HOST=https://ollama.com          # Ollama Cloud (pas de service local)
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_API_KEY=<clé Ollama Cloud>

JWT_SECRET=<openssl rand -hex 32>
ADMIN_PASSWORD=                      # laisser vide en prod
ADMIN_PASSWORD_HASH=<python backend/scripts/hash_password.py "motdepasse">
POSTGRES_PASSWORD=<secret>
CORS_ORIGINS=["https://app-cliente.com"]
```

### Lancer
```bash
docker compose --profile prod up --build -d
```
- Le service `migrate` applique les migrations **avant** le démarrage du backend (bloquant).
- Le **STT** est fourni par le serveur WhisperLive **en ligne** de l'équipe
  (`STT_BACKEND=whisperlive`, `WHISPERLIVE_URL=ws://srv-team-ia:9300`) : aucun service STT local
  à démarrer ni modèle Whisper à télécharger.
- Caddy obtient le certificat TLS et route `/v1`,`/admin/api`,`/health`,`/metrics` → backend,
  le reste → frontend.

### Vérifier
```bash
curl https://$DOMAIN/health
curl https://$DOMAIN/metrics
docker compose ps                    # tous les services « healthy »
```

---

## 3. Opérations courantes

| Tâche | Commande |
|-------|----------|
| Logs backend | `docker compose logs -f backend` (JSON structuré, sans contenu clinique) |
| Logs vocaux | `docker compose logs -f piper` (STT et LLM = services en ligne) |
| Migration DB | `docker compose run --rm migrate` (ou auto au démarrage) |
| Nouvelle migration | `cd backend && alembic revision --autogenerate -m "..."` |
| Sauvegarde DB | `docker compose exec db pg_dump -U $POSTGRES_USER voicetoform > backup.sql` |
| Restauration | `cat backup.sql \| docker compose exec -T db psql -U $POSTGRES_USER voicetoform` |
| Modèle LLM | Ollama Cloud (`OLLAMA_MODEL` dans `.env`) — rien à `pull` localement |
| Hash mot de passe admin | `cd backend && python scripts/hash_password.py "nouveau"` |
| Rotation `JWT_SECRET` | changer `.env` + redéployer → invalide sessions admin et jetons live en cours |
| Métriques latence | `curl https://$DOMAIN/metrics` |

---

## 4. Bascule dev → prod (rappel)
| | dev (profil `dev`) | prod (profil `prod`) |
|--|-----|------|
| Agent vocal | `SPEECH_AGENT=stub` | `SPEECH_AGENT=sandwich` |
| STT | `STT_BACKEND=stub` | `whisperlive` → serveur en ligne `ws://srv-team-ia:9300` |
| TTS | `TTS_BACKEND=stub` | `piper_http` → service `piper` |
| Agent/Extraction | `scripted` / `null` | `ollama` → Ollama Cloud (`https://ollama.com`) |
| Proxy/TLS | non | Caddy (service `proxy`) |
| Mot de passe admin | `ADMIN_PASSWORD` | `ADMIN_PASSWORD_HASH` (argon2) |

---

## 5. Données de santé — garanties (cf. EPIC 10)
- **Aucune** persistance d'audio ni de transcript ; la base ne contient que des métadonnées.
- Le **formulaire final** est purgé après `RESULT_RETENTION_SECONDS` (défaut 600 s).
- Piper (TTS) est auto-hébergé. ⚠️ **Ollama Cloud** (agent + extraction) est un **tiers** : le
  transcript transite par `ollama.com`. Pour « aucun envoi tiers », repasser à un Ollama auto-hébergé.
- Logs **sans** contenu clinique. Métriques = agrégats uniquement.

---

## 6. Dépannage
| Symptôme | Piste |
|----------|-------|
| Backend ne démarre pas | `migrate` a échoué → `docker compose logs migrate` (DB joignable ? `JWT_SECRET` ≥32 ?) |
| 401 sur `/admin/api/*` | jeton expiré → se reconnecter ; vérifier `ADMIN_PASSWORD(_HASH)` |
| WS `/v1/live` fermé 4401 | jeton éphémère expiré/rejoué → recréer une session |
| WS fermé 4403 | `Origin` non autorisé → ajouter au `allowed_origins` du compte ou `CORS_ORIGINS` |
| Agent muet (pas de voix) | service `piper` down ? `docker compose logs piper` ; `PIPER_URL` correct ? voix montée ? |
| STT ne transcrit rien | serveur en ligne joignable ? `WHISPERLIVE_URL=ws://srv-team-ia:9300` ? `STT_BACKEND=whisperlive` ? |
| Formulaire jamais rempli | `EXTRACTOR_BACKEND=ollama` ? `OLLAMA_HOST`/`OLLAMA_API_KEY` valides ? Sinon backend `null` |
| Latence élevée | STT/LLM distants saturés ou réseau lent → vérifier la connectivité `srv-team-ia`/`ollama.com` |
