import uuid


async def test_shopping_list_for_current_plan(client, make_user_complete):
    u = await make_user_complete()
    await client.post(
        "/api/v1/pantry/items", json={"items": [{"name": "spinach"}, {"name": "rice"}]}, headers=u.headers
    )
    await client.post(
        "/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer", "cream"]}, headers=u.headers
    )
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=u.headers)
    plan_id = r.json()["plan_id"]
    r = await client.get(f"/api/v1/plans/{plan_id}/shopping-list", headers=u.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1 and body["from_date"] <= body["to_date"]
    names = {i["name"].lower() for g in body["groups"] for i in g["items"]}
    assert "paneer" in names  # needed by the planned Palak paneer, not in the pantry
    assert "spinach" not in names  # on hand
    for g in body["groups"]:
        assert g["label"] and all(i["meals"] for i in g["items"])


async def test_shopping_list_unknown_or_foreign_plan_404(client, make_user_complete):
    a = await make_user_complete("A")
    b = await make_user_complete("B")
    assert (await client.get(f"/api/v1/plans/{uuid.uuid4()}/shopping-list", headers=a.headers)).status_code == 404
    await client.post("/api/v1/pantry/items", json={"items": [{"name": "rice"}]}, headers=a.headers)
    r = await client.post("/api/v1/plans/generate", json={"scope": "single", "mode": "week"}, headers=a.headers)
    assert (
        await client.get(f"/api/v1/plans/{r.json()['plan_id']}/shopping-list", headers=b.headers)
    ).status_code == 404
