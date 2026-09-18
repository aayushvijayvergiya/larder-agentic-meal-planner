import uuid

import jwt

from tests.conftest import TEST_JWT_SECRET, auth_headers


async def test_missing_token_401(client):
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_bad_token_401(client):
    r = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


async def test_wrong_audience_401(client):
    token = jwt.encode({"sub": str(uuid.uuid4()), "aud": "anon"}, TEST_JWT_SECRET, algorithm="HS256")
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_first_call_provisions_profile(client):
    uid = uuid.uuid4()
    r = await client.get("/api/v1/me", headers=auth_headers(uid, "new@example.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["id"] == str(uid)
    assert body["profile"]["email"] == "new@example.com"
    assert body["household"] is None
    assert body["onboarding_status"] == "pending"
    # second call is idempotent
    r2 = await client.get("/api/v1/me", headers=auth_headers(uid, "new@example.com"))
    assert r2.status_code == 200 and r2.json()["profile"]["id"] == str(uid)
