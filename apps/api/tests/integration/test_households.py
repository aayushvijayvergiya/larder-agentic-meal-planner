from larder.services.households import generate_invite


async def _invite(db_session, owner, **kw):
    inv = await generate_invite(db_session, owner.household, owner.profile.id, **kw)
    await db_session.commit()
    return inv.code


async def test_owner_creates_invite_and_member_joins(client, make_user_complete):
    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    r = await client.post(f"/api/v1/households/{owner.household.id}/invites", json={}, headers=owner.headers)
    assert r.status_code == 201 and len(r.json()["code"]) == 8
    code = r.json()["code"]
    r = await client.post("/api/v1/households/join", json={"code": code.lower()}, headers=joiner.headers)
    assert r.status_code == 200
    ids = {m["user_id"] for m in r.json()["members"]}
    assert ids == {str(owner.profile.id), str(joiner.profile.id)}
    r = await client.get("/api/v1/households/me", headers=joiner.headers)
    assert r.json()["id"] == str(owner.household.id)  # implicit household replaced
    invites = (await client.get(f"/api/v1/households/{owner.household.id}/invites", headers=owner.headers)).json()
    assert invites[0]["uses"] == 1


async def test_member_cannot_create_invite(client, make_user_complete):
    owner = await make_user_complete("Priya")
    other = await make_user_complete("Aarav")
    r = await client.post(f"/api/v1/households/{owner.household.id}/invites", json={}, headers=other.headers)
    assert r.status_code == 404  # wrong household => not found, never leak


async def test_expired_code_conflicts_and_unknown_is_404(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    code = await _invite(db_session, owner, expires_in_days=-1)
    r = await client.post("/api/v1/households/join", json={"code": code}, headers=joiner.headers)
    assert r.status_code == 409
    r = await client.post("/api/v1/households/join", json={"code": "ZZZZZZZZ"}, headers=joiner.headers)
    assert r.status_code == 404


async def test_cannot_join_from_non_implicit_household(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya")
    other = await make_user_complete("Aarav")
    await client.patch(f"/api/v1/households/{other.household.id}", json={"name": "Aarav's flat"}, headers=other.headers)
    code = await _invite(db_session, owner)
    r = await client.post("/api/v1/households/join", json={"code": code}, headers=other.headers)
    assert r.status_code == 409


async def test_remove_member_gives_new_implicit_household(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    code = await _invite(db_session, owner)
    await client.post("/api/v1/households/join", json={"code": code}, headers=joiner.headers)
    r = await client.delete(
        f"/api/v1/households/{owner.household.id}/members/{joiner.profile.id}", headers=owner.headers
    )
    assert r.status_code == 204
    r = await client.get("/api/v1/households/me", headers=joiner.headers)
    assert r.json()["is_implicit"] is True
    assert r.json()["members"][0]["preferred_view"] == "single"
    assert r.json()["name"] == "Aarav's kitchen"


async def test_member_can_leave_but_owner_cannot_leave_with_members(client, make_user_complete, db_session):
    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    code = await _invite(db_session, owner)
    await client.post("/api/v1/households/join", json={"code": code}, headers=joiner.headers)
    r = await client.delete(
        f"/api/v1/households/{owner.household.id}/members/{owner.profile.id}", headers=owner.headers
    )
    assert r.status_code == 409
    r = await client.delete(
        f"/api/v1/households/{owner.household.id}/members/{owner.profile.id}", headers=joiner.headers
    )
    assert r.status_code == 403
    r = await client.delete(
        f"/api/v1/households/{owner.household.id}/members/{joiner.profile.id}", headers=joiner.headers
    )
    assert r.status_code == 204


async def test_preferred_view_single_only_when_alone(client, make_user_complete):
    u = await make_user_complete()
    r = await client.patch(
        f"/api/v1/households/{u.household.id}/members/me", json={"preferred_view": "family"}, headers=u.headers
    )
    assert r.status_code == 422
    r = await client.patch(
        f"/api/v1/households/{u.household.id}/members/me", json={"preferred_view": "single"}, headers=u.headers
    )
    assert r.status_code == 200 and r.json()["preferred_view"] == "single"


async def test_patch_household_slots_and_schedule(client, make_user_complete):
    u = await make_user_complete()
    body = {
        "name": "Sharma kitchen",
        "slots": [
            {"key": "dinner", "label": "Dinner", "order": 2},
            {"key": "lunch", "label": "Lunch", "order": 1},
        ],
        "weekly_refresh_day": 5,
        "weekly_refresh_time": "20:00:00",
        "timezone": "Europe/London",
    }
    r = await client.patch(f"/api/v1/households/{u.household.id}", json=body, headers=u.headers)
    assert r.status_code == 200
    out = r.json()
    assert out["is_implicit"] is False and [s["key"] for s in out["slots"]] == ["lunch", "dinner"]
    assert out["weekly_refresh_day"] == 5 and out["timezone"] == "Europe/London"
    r = await client.patch(f"/api/v1/households/{u.household.id}", json={"timezone": "Mars/Olympus"}, headers=u.headers)
    assert r.status_code == 422
    dup = {"slots": [{"key": "a", "label": "A", "order": 1}, {"key": "a", "label": "B", "order": 2}]}
    assert (await client.patch(f"/api/v1/households/{u.household.id}", json=dup, headers=u.headers)).status_code == 422
