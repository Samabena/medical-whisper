"""Régénère backend/requirements-lock.txt.

Le lock épingle la fermeture transitive de `pip install -e ".[dev]"`
aux versions RÉELLEMENT installées dans l'environnement courant
(celles validées par la suite de tests).

Usage :
    python scripts/lock_deps.py

Pré-requis : l'environnement courant doit déjà avoir `pip install -e ".[dev]"`
appliqué (sinon les versions installées ne reflètent pas les déps du projet).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
LOCK = BACKEND / "requirements-lock.txt"
PROJECT_NAME = "voice-to-form-backend"

HEADER = (
    "# Lock file - voice-to-form-backend\n"
    "# Versions reellement installees et validees par la suite de tests.\n"
    "# Fermeture transitive de `pip install -e \".[dev]\"`.\n"
    "# Regenerer : python scripts/lock_deps.py\n"
    "# Installer  : pip install -r requirements-lock.txt && pip install -e . --no-deps\n"
)


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def closure_names() -> set[str]:
    """Noms de la fermeture transitive via le résolveur pip (dry-run)."""
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False, encoding="utf-8") as tmp:
        report_path = tmp.name
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "-e", ".[dev]",
            "--dry-run", "--ignore-installed", "--quiet",
            "--report", report_path,
        ],
        cwd=BACKEND, check=True,
    )
    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    Path(report_path).unlink(missing_ok=True)
    names = {_norm(i["metadata"]["name"]) for i in data["install"]}
    names.discard(_norm(PROJECT_NAME))
    return names


def installed_versions() -> dict[str, tuple[str, str]]:
    out = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--exclude-editable"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    res: dict[str, tuple[str, str]] = {}
    for line in out:
        if "==" in line:
            name, ver = line.split("==", 1)
            res[_norm(name)] = (name.strip(), ver.strip())
    return res


def main() -> int:
    closure = closure_names()
    installed = installed_versions()

    rows = [installed[k] for k in sorted(closure) if k in installed]
    missing = sorted(k for k in closure if k not in installed)

    LOCK.write_text(
        HEADER + "".join(f"{n}=={v}\n" for n, v in rows),
        encoding="utf-8",
    )
    print(f"WROTE {len(rows)} pinned packages -> {LOCK}")
    if missing:
        print("WARN non installes (lancer `pip install -e \".[dev]\"`) :", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
