"""INT-5.1 — authentification par clé API (compte résolu, révocation, compte inactif)."""

from __future__ import annotations

import pytest

from app.application.integration.authenticate import authenticate_api_key
from app.domain.entities import Account, ApiKey
from app.domain.errors import UnauthorizedError
from app.infrastructure.security.api_keys import generer_cle
from app.infrastructure.security.hashing import Sha256KeyHasher
from tests.fakes import InMemoryAccountRepo, InMemoryApiKeyRepo


async def test_cle_valide_revoquee_et_inconnue():
    accounts, keys, hasher = InMemoryAccountRepo(), InMemoryApiKeyRepo(), Sha256KeyHasher()
    compte = await accounts.add(Account(nom="A", email_contact="a@ex.com"))
    cle = generer_cle()
    k = await keys.add(ApiKey(account_id=compte.id, key_prefix=cle.key_prefix, key_hash=cle.key_hash))

    resolu = await authenticate_api_key(cle.cle_claire, accounts, keys, hasher)
    assert resolu.id == compte.id

    with pytest.raises(UnauthorizedError):
        await authenticate_api_key("fausse-cle", accounts, keys, hasher)

    await keys.revoke(k.id)
    with pytest.raises(UnauthorizedError):
        await authenticate_api_key(cle.cle_claire, accounts, keys, hasher)


async def test_compte_inactif_refuse():
    accounts, keys, hasher = InMemoryAccountRepo(), InMemoryApiKeyRepo(), Sha256KeyHasher()
    compte = await accounts.add(Account(nom="A", email_contact="a@ex.com", actif=False))
    cle = generer_cle()
    await keys.add(ApiKey(account_id=compte.id, key_prefix=cle.key_prefix, key_hash=cle.key_hash))
    with pytest.raises(UnauthorizedError):
        await authenticate_api_key(cle.cle_claire, accounts, keys, hasher)
