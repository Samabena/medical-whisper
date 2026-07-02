#!/usr/bin/env bash
# Déploie le(s) modèle(s) de voix Piper sur le serveur.
#
# Pourquoi : le dossier `voices/` est gitignoré (les .onnx font ~63 Mo) → il n'est PAS
# déployé par git clone/pull. Sans le fichier, Piper renvoie 500 « Unable to find voice ».
# Ce script copie les .onnx/.onnx.json locaux vers le bind-mount `voices/` du serveur.
#
# Usage (depuis la racine du dépôt, dans Git Bash / WSL / Linux) :
#   scripts/deploy_voice.sh [user] [host] [port] [remote_dir]
# Défauts adaptés au Pôle IA :
#   user=fanigue  host=37.27.71.61  port=5015  remote_dir=/srv/poleia/apps/medical-whisper/voices
#
# Pré-requis : ssh/scp fonctionnels vers le serveur (clé ou mot de passe), clé d'hôte
# déjà acceptée (sinon `ssh -p <port> <user>@<host>` une fois pour l'enregistrer).

set -euo pipefail

REMOTE_USER="${1:-fanigue}"
REMOTE_HOST="${2:-37.27.71.61}"
REMOTE_PORT="${3:-5015}"
REMOTE_DIR="${4:-/srv/poleia/apps/medical-whisper/voices}"
REMOTE_APP="$(dirname "$REMOTE_DIR")"   # dossier du docker-compose (parent de voices/)

# Dossier voices/ local (relatif à ce script → racine du dépôt).
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"
DEST="${REMOTE_USER}@${REMOTE_HOST}"
SSH=(ssh -p "$REMOTE_PORT")
SCP=(scp -P "$REMOTE_PORT")

echo "==> Voix locales : $LOCAL_DIR"
shopt -s nullglob
FICHIERS=("$LOCAL_DIR"/*.onnx "$LOCAL_DIR"/*.onnx.json)
if [ ${#FICHIERS[@]} -eq 0 ]; then
  echo "ERREUR : aucun fichier .onnx / .onnx.json dans $LOCAL_DIR" >&2
  exit 1
fi
printf '   - %s\n' "${FICHIERS[@]##*/}"

echo "==> Création du dossier distant ($DEST:$REMOTE_DIR, port $REMOTE_PORT)"
"${SSH[@]}" "$DEST" "mkdir -p '$REMOTE_DIR'"

echo "==> Copie (scp)…"
"${SCP[@]}" "${FICHIERS[@]}" "$DEST:$REMOTE_DIR/"

echo "==> Contenu distant :"
"${SSH[@]}" "$DEST" "ls -l '$REMOTE_DIR'"

echo "==> Test de synthèse Piper dans le conteneur (facultatif)…"
"${SSH[@]}" "$DEST" "cd '$REMOTE_APP' && docker compose exec -T piper sh -c \
  'printf \"Bonjour, test de la voix.\" | piper -m /voices/fr_FR-siwis-medium.onnx -f /tmp/o.wav && echo \"   Piper OK (\$(wc -c </tmp/o.wav) octets)\" || echo \"   Piper KO\"'" \
  || echo "   (test Piper ignoré — conteneur non démarré ou compose indisponible)"

echo "==> Terminé. La voix est en place ; Piper la lit à chaud (aucun redémarrage requis)."
