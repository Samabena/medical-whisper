"""Génère un hash argon2 pour ADMIN_PASSWORD_HASH (prod).

Usage :
    python scripts/hash_password.py "mon-mot-de-passe-fort"
puis copier la sortie dans .env :  ADMIN_PASSWORD_HASH=<hash>  (et laisser ADMIN_PASSWORD vide).
"""

from __future__ import annotations

import sys

from argon2 import PasswordHasher


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage : python scripts/hash_password.py <mot_de_passe>", file=sys.stderr)
        return 1
    print(PasswordHasher().hash(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
