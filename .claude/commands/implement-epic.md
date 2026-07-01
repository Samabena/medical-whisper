Implémente tous les tickets de l'EPIC **$ARGUMENTS** dans l'ordre défini dans `BACKLOG.md`.

## EPICs disponibles

| Argument | Tickets inclus                        |
|----------|---------------------------------------|
| `0`      | INFRA-1, INFRA-2                      |
| `1`      | CORE-1, CORE-2, CORE-3                |
| `2`      | FORM-1, FORM-2, FORM-3                |
| `3`      | STW-1                                 |
| `4`      | CLAR-1, CLAR-2                        |
| `5`      | SESS-1, SESS-2, SESS-3, SESS-4        |
| `6`      | OPS-1, OPS-2, OPS-3, OPS-4           |

## Étapes

Pour chaque ticket de l'epic, dans l'ordre :

1. Implémente le ticket (mêmes règles que `/implement-ticket`).
2. Lance `pytest tests/ -m "not integration" -v`.
3. Si les tests échouent → corrige avant de passer au suivant.
4. Commit : `[TICKET-ID] <description courte>`.
5. Passe au ticket suivant de l'epic.

**Stop immédiat** si un ticket ne peut pas être complété (dépendance absente, erreur bloquante) — signale clairement ce qui bloque avant de t'arrêter.

## Ordre global recommandé (si tu enchaînes les epics)

EPIC 0 → 1 → 2 → 3 → 4 → 5 → 6 → (7 plus tard)
