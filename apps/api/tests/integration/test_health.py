async def test_health_reports_provider(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["llm_provider"] == "fake"
    assert body["database"] == "ok"
