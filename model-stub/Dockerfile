# Stub du serveur modèle PersonaPlex — placeholder EPIC 0.
# En dev, l'agent vocal scripté tourne IN-PROCESS dans le backend (SPEECH_AGENT=stub) ;
# ce conteneur fournira un faux endpoint WebSocket pour tester l'adapter
# `personaplex_client` localement (implémenté à l'EPIC 6.2).
FROM python:3.11-slim
WORKDIR /srv
RUN pip install --no-cache-dir "websockets>=12.0"
COPY server.py ./
EXPOSE 8998
CMD ["python", "server.py"]
