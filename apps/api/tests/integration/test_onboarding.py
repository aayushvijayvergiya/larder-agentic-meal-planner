import uuid

from tests.agents.test_onboarding_flow import ANSWERS
from tests.conftest import auth_headers


async def _answer_all(client, headers):
    t = (await client.post("/api/v1/onboarding/start", headers=headers)).json()
    while not t["is_complete"]:
        body = {"thread_id": t["thread_id"], "answer": {"kind": "widget", "value": ANSWERS[t["field"]]}}
        r = await client.post("/api/v1/onboarding/turn", json=body, headers=headers)
        assert r.status_code == 200, r.text
        t = r.json()
    return t


async def test_start_is_idempotent_and_state_persists(client):
    h = auth_headers(uuid.uuid4())
    a = (await client.post("/api/v1/onboarding/start", headers=h)).json()
    assert a["field"] == "display_name" and a["widget"]["type"] == "text"
    me = (await client.get("/api/v1/me", headers=h)).json()
    assert me["onboarding_status"] == "in_progress"
    r = await client.post(
        "/api/v1/onboarding/turn",
        json={"thread_id": a["thread_id"], "answer": {"kind": "widget", "value": "Priya"}},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["field"] == "date_of_birth"
    b = (await client.post("/api/v1/onboarding/start", headers=h)).json()
    assert b["field"] == "date_of_birth" and b["draft"]["display_name"] == "Priya"
    assert b["progress"] == {"answered": 1, "total": 15}


async def test_wrong_thread_is_404(client):
    h = auth_headers(uuid.uuid4())
    await client.post("/api/v1/onboarding/start", headers=h)
    r = await client.post(
        "/api/v1/onboarding/turn",
        json={"thread_id": "onb_other", "answer": {"kind": "widget", "value": "x"}},
        headers=h,
    )
    assert r.status_code == 404


async def test_complete_before_finishing_conflicts(client):
    h = auth_headers(uuid.uuid4())
    t = (await client.post("/api/v1/onboarding/start", headers=h)).json()
    r = await client.post("/api/v1/onboarding/complete", json={"thread_id": t["thread_id"]}, headers=h)
    assert r.status_code == 409


async def test_complete_creates_profile_and_implicit_household(client):
    h = auth_headers(uuid.uuid4())
    t = await _answer_all(client, h)
    assert t["widget"]["type"] == "review"
    r = await client.post(
        "/api/v1/onboarding/complete",
        json={"thread_id": t["thread_id"], "overrides": {"likes": ["paneer", "rajma"]}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["onboarding_status"] == "complete"
    assert body["profile"]["likes"] == ["paneer", "rajma"]
    assert body["profile"]["display_name"] == "Priya" and body["profile"]["max_prep_minutes"] == 30
    assert body["profile"]["medical_conditions"] == [{"name": "type 2 diabetes", "notes": None}]
    assert body["household"]["is_implicit"] is True and body["household"]["name"] == "Priya's kitchen"
    assert body["household"]["members"][0]["preferred_view"] == "single"
    assert (await client.post("/api/v1/onboarding/start", headers=h)).status_code == 409
    # completing again is idempotent
    r = await client.post("/api/v1/onboarding/complete", json={"thread_id": t["thread_id"]}, headers=h)
    assert r.status_code == 200 and r.json()["first_plan_job_id"] is None
    me = (await client.get("/api/v1/me", headers=h)).json()
    assert me["household"]["id"] == body["household"]["id"]


async def test_household_endpoints_blocked_before_onboarding(client):
    h = auth_headers(uuid.uuid4())
    r = await client.get("/api/v1/pantry", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "onboarding_incomplete"
