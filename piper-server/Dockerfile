# Serveur TTS Piper — HTTP, CPU (aucun GPU requis). Expose :5000.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUTF8=1

# espeak-ng : phonémisation utilisée par Piper (voix multilingues, accents FR corrects).
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
RUN pip install --upgrade pip && pip install "piper-tts>=1.2"
COPY server.py ./

EXPOSE 5000

# La voix .onnx est fournie via un volume (voir docker-compose : ./voices → /voices).
ENV PIPER_VOICE=/voices/fr_FR-siwis-medium.onnx
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "5000"]
