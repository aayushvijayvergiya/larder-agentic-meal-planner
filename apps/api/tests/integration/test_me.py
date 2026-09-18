async def test_me_includes_household_after_onboarding(client, make_user_complete):
    u = await make_user_complete()
    r = await client.get("/api/v1/me", headers=u.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["household"]["id"] == str(u.household.id)
    assert body["household"]["members"][0]["display_name"] == "Priya"
    assert [s["key"] for s in body["household"]["slots"]] == ["breakfast", "lunch", "snack", "dinner"]


async def test_patch_me_updates_fields(client, make_user_complete):
    u = await make_user_complete()
    body = {
        "height_cm": 172,
        "dislikes": ["Bitter Gourd", "bitter gourd", "Mushrooms"],
        "cuisines": ["North Indian", "Gujarati"],
        "medical_conditions": [{"name": "Type 2 diabetes", "notes": "avoid refined sugar"}],
    }
    r = await client.patch("/api/v1/me", json=body, headers=u.headers)
    assert r.status_code == 200
    out = r.json()
    assert out["height_cm"] == 172
    assert out["dislikes"] == ["bitter gourd", "mushroom"]
    assert out["cuisines"] == ["north_indian", "gujarati"]
    assert out["medical_conditions"] == [{"name": "Type 2 diabetes", "notes": "avoid refined sugar"}]


async def test_patch_me_rejects_out_of_range(client, make_user_complete):
    u = await make_user_complete()
    r = await client.patch("/api/v1/me", json={"height_cm": 900}, headers=u.headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
