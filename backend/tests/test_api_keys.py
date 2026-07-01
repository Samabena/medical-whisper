"""DATA-1.4 — génération/hachage des clés API."""

from __future__ import annotations

from app.infrastructure.security.api_keys import generer_cle, hacher, masquer, prefixe


def test_generation_unique_et_coherente():
    a = generer_cle()
    b = generer_cle()
    assert a.cle_claire != b.cle_claire            # haute entropie
    assert a.key_hash == hacher(a.cle_claire)      # hash reproductible
    assert a.key_prefix == prefixe(a.cle_claire)   # préfixe = début de la clé
    assert len(a.key_hash) == 64                   # SHA-256 hex


def test_hash_deterministe_et_clair_non_stocke():
    cle = generer_cle()
    # Le hash ne permet pas de retrouver la clé ; le masque n'expose que le préfixe.
    assert cle.cle_claire not in masquer(cle.key_prefix)
    assert masquer(cle.key_prefix).startswith(cle.key_prefix)
