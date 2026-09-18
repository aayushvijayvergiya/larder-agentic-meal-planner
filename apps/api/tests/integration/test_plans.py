import uuid

from tests.conftest import auth_headers
from tests.integration.test_onboarding import _answer_all


async def _seed(client, u):
    names = ["spinach", "paneer", "rice", "toor dal", "onion"]
    await client.post("/api/v1/pantry/items", json={"items": [{"name": n} for n in names]}, headers=u.headers)
    await client.post(
        "/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer"]}, headers=u.headers
    )


async def test_generate_week_then_current(client, make_user_complete):
    u = await make_user_complete()
    await _seed(client, u)
    assert (await client.get("/api/v1/plans/current", headers=u.headers)).json() == {"plan": None, "active_job": None}
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    assert r.status_code == 202, r.text
    job = (await client.get(f"/api/v1/plans/jobs/{r.json()['job_id']}", headers=u.headers)).json()
    assert job["status"] == "ready" and job["error"] is None and job["finished_at"] is not None
    cur = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    plan = cur["plan"]
    assert plan["id"] == r.json()["plan_id"] and len(plan["days"]) == 7
    assert len(plan["days"][0]["entries"]) == 4 and cur["active_job"] is None
    entry = plan["days"][0]["entries"][0]
    assert entry["slot_label"] == "Breakfast" and entry["reason"] and entry["meal"]["name"]
    assert entry["my_feedback"] is None and entry["cooked_count"] == 0
    assert plan["coverage"]["needed"] >= plan["coverage"]["on_hand"] > 0
    assert isinstance(plan["unused_pantry"], list)
    # default scope falls back to the member's preferred view (single)
    assert (await client.get("/api/v1/plans/current", headers=u.headers)).json()["plan"]["id"] == plan["id"]


async def test_family_scope_rejected_when_alone(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/plans/generate", json={"scope": "family", "mode": "week"}, headers=u.headers)
    assert r.status_code == 422
    assert (await client.get("/api/v1/plans/current?scope=family", headers=u.headers)).status_code == 422


async def test_today_requires_existing_plan(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "today"}, headers=u.headers)
    assert r.status_code == 404


async def test_swap_entry_and_feedback_visible(client, make_user_complete):
    u = await make_user_complete()
    await _seed(client, u)
    await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    cur = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    entry = cur["plan"]["days"][0]["entries"][3]
    r = await client.post(
        f"/api/v1/plans/{cur['plan']['id']}/entries/{entry['id']}/swap", json={"reason": "too heavy"}, headers=u.headers
    )
    assert r.status_code == 202
    assert (await client.get(f"/api/v1/plans/jobs/{r.json()['job_id']}", headers=u.headers)).json()["status"] == "ready"
    cur2 = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    new_entry = cur2["plan"]["days"][0]["entries"][3]
    assert new_entry["id"] != entry["id"]
    ids_before = [e["id"] for d in cur["plan"]["days"] for e in d["entries"] if e["id"] != entry["id"]]
    ids_after = [e["id"] for d in cur2["plan"]["days"] for e in d["entries"] if e["id"] != new_entry["id"]]
    assert ids_before == ids_after
    # feedback on the planned meal shows up on the entry
    mid = new_entry["meal"]["id"]
    await client.post(
        f"/api/v1/meals/{mid}/feedback", json={"kind": "up", "plan_entry_id": new_entry["id"]}, headers=u.headers
    )
    await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "cooked"}, headers=u.headers)
    cur3 = (await client.get("/api/v1/plans/current?scope=single", headers=u.headers)).json()
    e3 = cur3["plan"]["days"][0]["entries"][3]
    assert e3["my_feedback"] == "up" and e3["cooked_count"] == 1 and e3["meal"]["feedback"]["up"] == 1


async def test_swap_wrong_plan_or_entry_404(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post(f"/api/v1/plans/{uuid.uuid4()}/entries/{uuid.uuid4()}/swap", json={}, headers=u.headers)
    assert r.status_code == 404


async def test_new_week_supersedes_overlap(client, make_user_complete, db_session):
    u = await make_user_complete()
    await _seed(client, u)
    a = (
        await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    ).json()["plan_id"]
    b = (
        await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    ).json()["plan_id"]
    from larder.db.models import MealPlan

    assert (await db_session.get(MealPlan, uuid.UUID(a))).status == "superseded" and a != b
    assert (await client.get("/api/v1/plans/current", headers=u.headers)).json()["plan"]["id"] == b


async def test_today_mode_regenerates_only_today(client, make_user_complete):
    u = await make_user_complete()
    await _seed(client, u)
    await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    cur = (await client.get("/api/v1/plans/current", headers=u.headers)).json()
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "today"}, headers=u.headers)
    assert r.status_code == 202 and r.json()["plan_id"] == cur["plan"]["id"]
    cur2 = (await client.get("/api/v1/plans/current", headers=u.headers)).json()
    day0_before = {e["id"] for e in cur["plan"]["days"][0]["entries"]}
    day0_after = {e["id"] for e in cur2["plan"]["days"][0]["entries"]}
    rest_before = [e["id"] for d in cur["plan"]["days"][1:] for e in d["entries"]]
    rest_after = [e["id"] for d in cur2["plan"]["days"][1:] for e in d["entries"]]
    assert day0_before.isdisjoint(day0_after) and rest_before == rest_after


async def test_job_failure_is_recorded(client, make_user_complete, monkeypatch):
    u = await make_user_complete()
    await _seed(client, u)
    from larder.jobs import runner

    async def boom(*args, **kwargs):
        raise RuntimeError("planner exploded")

    monkeypatch.setattr(runner, "run_planner", boom)
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    job = (await client.get(f"/api/v1/plans/jobs/{r.json()['job_id']}", headers=u.headers)).json()
    assert job["status"] == "failed" and "planner exploded" in job["error"]
    assert (await client.get("/api/v1/plans/current", headers=u.headers)).json()["plan"] is None


async def test_job_not_visible_across_households(client, make_user_complete):
    a = await make_user_complete("A")
    b = await make_user_complete("B")
    await _seed(client, a)
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=a.headers)
    assert (await client.get(f"/api/v1/plans/jobs/{r.json()['job_id']}", headers=b.headers)).status_code == 404


async def test_onboarding_complete_enqueues_first_plan(client):
    h = auth_headers(uuid.uuid4())
    t = await _answer_all(client, h)
    r = await client.post("/api/v1/onboarding/complete", json={"thread_id": t["thread_id"]}, headers=h)
    assert r.status_code == 200 and r.json()["first_plan_job_id"] is not None
    cur = (await client.get("/api/v1/plans/current", headers=h)).json()
    assert cur["plan"] is not None and len(cur["plan"]["days"]) == 7


async def test_removed_member_gets_a_fresh_plan(client, make_user_complete, db_session):
    from larder.services.households import generate_invite

    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    inv = await generate_invite(db_session, owner.household, owner.profile.id)
    await db_session.commit()
    await client.post("/api/v1/households/join", json={"code": inv.code}, headers=joiner.headers)
    r = await client.delete(
        f"/api/v1/households/{owner.household.id}/members/{joiner.profile.id}", headers=owner.headers
    )
    assert r.status_code == 204
    cur = (await client.get("/api/v1/plans/current", headers=joiner.headers)).json()
    assert cur["plan"] is not None
