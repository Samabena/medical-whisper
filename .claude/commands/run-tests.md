Lance la suite de tests pytest pour **voice-to-form**.

## Argument `$ARGUMENTS` (optionnel)

| Valeur         | Comportement                                              |
|----------------|-----------------------------------------------------------|
| *(vide)*       | Tests unitaires uniquement (sans marqueur `integration`)  |
| `unit`         | Idem vide                                                 |
| `integration`  | Tests d'intégration uniquement (services réels requis)    |
| `all`          | Tous les tests                                            |
| `<TICKET-ID>`  | Fichier de test lié au ticket (ex : `CORE-1` → `tests/test_extraction.py` selon le mapping) |

## Mapping ticket → fichier de test

| Ticket(s)              | Fichier                         |
|------------------------|---------------------------------|
| INFRA-1                | `tests/test_health.py`          |
| FORM-1, FORM-2, FORM-3 | `tests/test_forms_catalog.py`   |
| STW-1                  | `tests/test_extraction.py`      |
| CLAR-1, CLAR-2         | `tests/test_clarification.py`   |
| SESS-1 à SESS-4        | `tests/test_session_flow.py`    |

## Commandes à lancer

- Unitaires : `pytest tests/ -m "not integration" -v`
- Intégration : `pytest tests/ -m integration -v`
- Tout : `pytest tests/ -v`
- Fichier ciblé : `pytest tests/<fichier> -v`

Affiche un résumé : nombre passés / échoués / skippés, et la commande exacte utilisée.
