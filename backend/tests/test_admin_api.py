"""SEC-2.1 — routeur admin : login, refresh, route protégée /me."""

from __future__ import annotations


def test_login_correct_puis_me(client):
    r = client.post("/admin/api/login", json={"password": "test-admin-password"})
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    # Route protégée accessible avec le Bearer.
    me = client.get("/admin/api/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200 and me.json() == {"admin": "admin@local"}


def test_login_incorrect_401(client):
    r = client.post("/admin/api/login", json={"password": "mauvais"})
    assert r.status_code == 401


def test_me_sans_jeton_401(client):
    assert client.get("/admin/api/me").status_code == 401


def test_refresh_donne_un_nouvel_access(client):
    login = client.post("/admin/api/login", json={"password": "test-admin-password"}).json()
    r = client.post("/admin/api/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    access = r.json()["access_token"]
    me = client.get("/admin/api/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
