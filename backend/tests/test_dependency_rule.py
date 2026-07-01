"""CORE-0.1 — garde-fou de la Clean Architecture (règle de dépendance).

Le domaine ne doit dépendre de RIEN d'externe (ni FastAPI, ni SQLAlchemy, ni l'infra).
La couche application ne doit pas connaître l'interface ni l'infrastructure.
On vérifie statiquement les imports via l'AST (aucun import dynamique requis).
"""

from __future__ import annotations

import ast
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[1] / "app"

# Modules interdits par couche (préfixes d'import).
_INTERDITS_DOMAIN = ("fastapi", "starlette", "sqlalchemy", "redis", "pydantic_settings",
                     "app.application", "app.infrastructure", "app.interface")
_INTERDITS_APPLICATION = ("fastapi", "starlette", "sqlalchemy", "redis",
                          "app.infrastructure", "app.interface")


def _imports_du_module(chemin: Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name for darg in [noeud] for alias in darg.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.add(noeud.module)
    return noms


def _fichiers(sous_dossier: str) -> list[Path]:
    return list((_RACINE / sous_dossier).rglob("*.py"))


def _violations(fichiers: list[Path], interdits: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for fichier in fichiers:
        for imp in _imports_du_module(fichier):
            if any(imp == i or imp.startswith(i + ".") for i in interdits):
                violations.append(f"{fichier.relative_to(_RACINE)} importe {imp!r}")
    return violations


def test_domaine_sans_dependance_externe():
    violations = _violations(_fichiers("domain"), _INTERDITS_DOMAIN)
    assert not violations, "Le domaine doit rester pur :\n" + "\n".join(violations)


def test_application_ignore_infrastructure_et_interface():
    violations = _violations(_fichiers("application"), _INTERDITS_APPLICATION)
    assert not violations, "L'application ne doit pas dépendre des couches externes :\n" + "\n".join(
        violations
    )
