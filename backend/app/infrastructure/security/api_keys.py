"""Génération et hachage des clés API (DATA-1.4).

Les clés sont des secrets **à haute entropie** (`token_urlsafe`) : un hachage SHA-256
rapide suffit (contrairement aux mots de passe humains qui exigent argon2, cf. EPIC 2).
La clé en clair n'est connue qu'au moment de la création — seul le hash est stocké.
Un préfixe non secret est conservé pour l'affichage et accélérer la recherche.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

PREFIX_LEN = 8


def hacher(cle_claire: str) -> str:
    return hashlib.sha256(cle_claire.encode("utf-8")).hexdigest()


def prefixe(cle_claire: str) -> str:
    return cle_claire[:PREFIX_LEN]


def masquer(key_prefix: str) -> str:
    """Représentation affichable d'une clé révoquée/listée (jamais la clé entière)."""
    return f"{key_prefix}…"


@dataclass(frozen=True)
class CleGeneree:
    cle_claire: str   # affichée UNE seule fois à l'appelant
    key_prefix: str
    key_hash: str


def generer_cle() -> CleGeneree:
    """Crée une nouvelle clé API. Retourne la clé en clair + ses dérivés à persister."""
    cle = secrets.token_urlsafe(32)
    return CleGeneree(cle_claire=cle, key_prefix=prefixe(cle), key_hash=hacher(cle))
