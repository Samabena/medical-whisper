# Mode DEV local — tester le rendu et le résultat sans GPU

PersonaPlex-7B (speech-to-speech, base Moshi) exige un GPU A100/H100 : **impossible en
local** sur une machine sans GPU NVIDIA. Ce mode dev le remplace par un **LLM texte via
Ollama** qui (a) joue l'agent conversationnel selon la persona et (b) extrait les champs
du formulaire. On teste ainsi *qualité du dialogue + remplissage + résultat final* en
local, sans Docker ni GPU.

## Prérequis

- **Ollama Cloud** : une clé API (`OLLAMA_API_KEY`) avec `OLLAMA_HOST=https://ollama.com`.
  Modèle par défaut : `gpt-oss:120b-cloud` (dialogue **et** extraction). Vérifié OK ;
  `qwen3.5:cloud`/`cogito` nécessitent un abonnement / sont retirés.
  *Alternative :* un Ollama local (`ollama signin`) avec `OLLAMA_HOST=http://localhost:11434`
  relaie aussi vers le cloud sans clé.
- **Backend** : venv `backend/.venv` (déjà présent). **Front** : `frontend/` (Node 24).

> 💡 **Reconstruire l'env backend** (déps figées). Toujours lancer pytest/uvicorn via
> `.venv\Scripts\python.exe` — *pas* le `python` global, qui n'a pas les déps.
> ```bash
> cd backend
> python -m venv .venv                              # si absent
> .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
> .venv\Scripts\python.exe -m pip install -e . --no-deps
> ```
> Régénérer le lock après une mise à jour de déps : `.venv\Scripts\python.exe scripts\lock_deps.py`

> ⚠️ `gpt-oss` n'applique pas strictement le `format=schema` d'Ollama et enrobe parfois
> le JSON dans un bloc ```` ```json ````. L'extracteur a été rendu tolérant (parsing
> robuste). Pour un JSON strictement contraint en prod, préférer un Ollama auto-hébergé
> avec un modèle qui supporte les sorties structurées (ex. `llama3.1`).

## Configuration

Tout est déjà dans `backend/.env` (créé pour ce mode) :

```
DATABASE_URL=sqlite+aiosqlite:///./dev.db   # pas de Postgres requis
SPEECH_AGENT=llm                            # agent conversationnel LLM
EXTRACTOR_BACKEND=ollama                     # remplissage réel du formulaire
OLLAMA_HOST=https://ollama.com               # Ollama Cloud (clé API)
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_API_KEY=<clé Ollama Cloud>
```

## Lancer (3 terminaux)

```bash
# 1) Seed : crée la base SQLite + un compte + un formulaire publié + une clé API
cd backend
.venv\Scripts\python.exe scripts\seed_dev.py     # imprime la CLÉ API à coller

# 2) Backend (API + WebSocket live)
.venv\Scripts\python.exe -m uvicorn app.interface.main:app --reload --port 8000

# 3) Frontend (console de test)
cd frontend
npm install        # première fois seulement
npm run dev        # http://localhost:5173
```

## Tester

1. Ouvre http://localhost:5173, connecte-toi (**admin@local / admin1234**).
2. Va sur **Console de test live**.
3. Colle la **clé API** imprimée par le seed → **Charger** → choisis *Consultation médicale*.
4. **Démarrer** : l'agent salue et pose sa première question.
5. **Tape** ce que dirait le médecin (ex. « Le patient s'appelle Jean Dupont, 54 ans,
   il consulte pour une migraine sévère, c'est urgent »). À chaque tour :
   - l'**agent répond** une question contextuelle (qualité du dialogue),
   - le **formulaire se remplit** en direct (champs + niveau de confiance),
   - quand tous les champs requis sont « confiant », la session se **clôture** et le
     **résultat final** s'affiche.

## Remettre en stub / prod

- Dialogue scripté déterministe (offline total) : `SPEECH_AGENT=stub`, `EXTRACTOR_BACKEND=null`.
- Vocal réel : `SPEECH_AGENT=sandwich`, `STT_BACKEND=whisperlive`,
  `WHISPERLIVE_URL=ws://srv-team-ia:9300` (serveur STT en ligne de l'équipe).
