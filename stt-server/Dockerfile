# Serveur STT « sandwich » — faster-whisper sur CPU (aucun GPU requis).
# Expose un WebSocket compatible WhisperLive (sous-ensemble) sur :9090.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Cache des modèles Hugging Face (monté en volume → téléchargé une seule fois).
    HF_HOME=/models

# libgomp1 : requis par ctranslate2 (moteur de faster-whisper) au runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY server.py ./

EXPOSE 9090

# WHISPER_MODEL surchargeable (small en dev CPU, large-v3 si CPU costaud / prod).
ENV WHISPER_MODEL=small
CMD ["sh", "-c", "python server.py --host 0.0.0.0 --port 9090 --model ${WHISPER_MODEL}"]
