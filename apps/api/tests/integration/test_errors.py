from pydantic import BaseModel

from larder.errors import ApiError


async def test_api_error_envelope(client):
    app = client._transport.app

    @app.get("/boom")
    async def boom():
        raise ApiError("conflict", 409, "already there", {"field": "name"})

    r = await client.get("/boom")
    assert r.status_code == 409
    assert r.json() == {"error": {"code": "conflict", "message": "already there", "details": {"field": "name"}}}
    assert "x-request-id" in r.headers


async def test_request_validation_envelope(client):
    app = client._transport.app

    class In(BaseModel):
        n: int

    @app.post("/echo")
    async def echo(body: In):
        return body

    r = await client.post("/echo", json={"n": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]["errors"][0]["loc"] == ["body", "n"]


async def test_request_id_is_propagated_when_supplied(client):
    r = await client.get("/api/v1/health", headers={"X-Request-Id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
