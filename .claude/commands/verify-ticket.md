Vérifie que le ticket **$ARGUMENTS** satisfait tous ses critères d'acceptation définis dans `BACKLOG.md`.

## Étapes

1. Lis `BACKLOG.md` — extrait la section **Acceptation** du ticket `$ARGUMENTS`.
2. Parcours les fichiers implémentés correspondants (voir arborescence dans BACKLOG).
3. Lance `pytest tests/ -m "not integration" -v`.
4. Si les services réels sont disponibles (`.env` renseigné), lance aussi `pytest tests/ -m integration -v`.
5. Pour chaque critère d'acceptation, indique :
   - ✅ **Satisfait** — fichier:ligne de la preuve
   - ❌ **Non satisfait** — ce qui manque et correction minimale suggérée
6. Synthèse finale : ticket **DONE** ou liste des points bloquants.
