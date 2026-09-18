async def _add(client, headers, *names):
    return await client.post("/api/v1/pantry/items", json={"items": [{"name": n} for n in names]}, headers=headers)


async def test_bulk_add_groups_and_dedupes(client, make_user_complete):
    u = await make_user_complete()
    body = {
        "items": [
            {"name": "Paneer"},
            {"name": "paneer "},
            {"name": "Toor dal"},
            {"name": "Spinach", "category": "vegetables"},
        ]
    }
    r = await client.post("/api/v1/pantry/items", json=body, headers=u.headers)
    assert r.status_code == 201
    assert len(r.json()["created"]) == 3 and r.json()["existing"] == []
    r = await client.get("/api/v1/pantry", headers=u.headers)
    cats = {c["category"]: [i["name"] for i in c["items"]] for c in r.json()["categories"]}
    assert cats == {"vegetables": ["Spinach"], "dairy": ["Paneer"], "pulses": ["Toor dal"]}
    assert [c["category"] for c in r.json()["categories"]] == ["vegetables", "dairy", "pulses"]
    assert r.json()["total"] == 3


async def test_re_adding_unavailable_item_flips_available(client, make_user_complete):
    u = await make_user_complete()
    r = await _add(client, u.headers, "Onion")
    item_id = r.json()["created"][0]["id"]
    r = await client.patch(f"/api/v1/pantry/items/{item_id}", json={"is_available": False}, headers=u.headers)
    assert r.status_code == 200 and r.json()["is_available"] is False
    r = await _add(client, u.headers, "onion")
    assert r.json()["created"] == []
    assert r.json()["existing"][0]["is_available"] is True


async def test_unknown_item_goes_to_other_with_fake_llm(client, make_user_complete):
    u = await make_user_complete()
    r = await _add(client, u.headers, "gundruk")
    assert r.json()["created"][0]["category"] == "other"


async def test_rename_conflict_and_delete(client, make_user_complete):
    u = await make_user_complete()
    r = await _add(client, u.headers, "Onion", "Tomato")
    onion, tomato = r.json()["created"]
    r = await client.patch(f"/api/v1/pantry/items/{onion['id']}", json={"name": "tomatoes"}, headers=u.headers)
    assert r.status_code == 409
    r = await client.patch(f"/api/v1/pantry/items/{onion['id']}", json={"name": "Red onion"}, headers=u.headers)
    assert r.status_code == 200 and r.json()["name"] == "Red onion"
    assert (await client.delete(f"/api/v1/pantry/items/{tomato['id']}", headers=u.headers)).status_code == 204
    assert (await client.get("/api/v1/pantry", headers=u.headers)).json()["total"] == 1


async def test_other_household_cannot_touch_item(client, make_user_complete):
    a = await make_user_complete("A")
    b = await make_user_complete("B")
    r = await _add(client, a.headers, "Onion")
    item_id = r.json()["created"][0]["id"]
    assert (await client.delete(f"/api/v1/pantry/items/{item_id}", headers=b.headers)).status_code == 404
    r = await client.patch(f"/api/v1/pantry/items/{item_id}", json={"is_available": False}, headers=b.headers)
    assert r.status_code == 404


async def test_suggestions_exclude_present(client, make_user_complete):
    u = await make_user_complete()
    await _add(client, u.headers, "onion")
    r = await client.get("/api/v1/pantry/suggestions", headers=u.headers)
    names = [i["name"] for i in r.json()["items"]]
    assert "onion" not in names and "tomato" in names and len(names) >= 59


async def test_empty_or_blank_names_rejected(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post("/api/v1/pantry/items", json={"items": [{"name": "   "}]}, headers=u.headers)
    assert r.status_code == 422
    r = await client.post("/api/v1/pantry/items", json={"items": []}, headers=u.headers)
    assert r.status_code == 422
