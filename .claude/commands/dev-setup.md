Configure l'environnement de développement local pour **voice-to-form**.

## Étapes

1. Vérifie que Python 3.10+ est disponible (`python --version`).
2. Crée un venv si absent :
   ```
   python -m venv venv
   venv\Scripts\activate   # Windows
   # ou : source venv/bin/activate  (Linux/Mac)
   ```
3. Installe les dépendances :
   ```
   pip install -r requirements.txt
   ```
4. Copie `.env.example` → `.env` si `.env` absent, puis renseigne a minima :
   - `OLLAMA_API_KEY` (clé Ollama Cloud)
   - `PIPER_VOICE_PATH` (chemin vers la voix Piper téléchargée)
5. Télécharge la voix Piper française si absente :
   ```
   python -m piper.download_voices fr_FR-siwis-medium --data-dir <PIPER_VOICE_PATH>
   ```
6. Démarre le service :
   ```
   uvicorn app.main:app --reload
   ```
7. Vérifie `GET /health` → `{"status":"ok"}`.
8. Lance les tests unitaires : `pytest tests/ -m "not integration" -v`.

## Signalement

À la fin, liste les étapes manuelles restantes (clés API manquantes, modèles non téléchargés, ports occupés, etc.).
