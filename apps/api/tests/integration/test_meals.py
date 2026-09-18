from larder.llm.base import LLMError


async def test_create_meal_enriches(client, make_user_complete):
    u = await make_user_complete()
    r = await client.post(
        "/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer"]}, headers=u.headers
    )
    assert r.status_code == 201
    m = r.json()
    assert m["enrichment_status"] == "complete" and m["source"] == "user"
    assert {i["name"] for i in m["ingredients"]} >= {"spinach", "paneer"}
    assert "dairy" in m["allergens"] and m["diet_tags"] == ["vegetarian"]
    assert m["feedback"] == {"up": 0, "down": 0, "cooked": 0, "last_cooked_at": None}


async def test_duplicate_name_conflicts(client, make_user_complete):
    u = await make_user_complete()
    await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)
    assert (await client.post("/api/v1/meals", json={"name": "dal "}, headers=u.headers)).status_code == 409


async def test_enrichment_failure_saves_raw_and_can_retry(client, make_user_complete, fake_llm):
    u = await make_user_complete()
    fake_llm.fail_next(LLMError("down"))
    r = await client.post(
        "/api/v1/meals", json={"name": "Khichdi", "ingredients": ["rice", "moong dal"]}, headers=u.headers
    )
    assert r.status_code == 201
    assert r.json()["enrichment_status"] == "failed"
    assert [i["name"] for i in r.json()["ingredients"]] == ["rice", "moong dal"]
    r = await client.post(f"/api/v1/meals/{r.json()['id']}/enrich", headers=u.headers)
    assert r.status_code == 200 and r.json()["enrichment_status"] == "complete"


async def test_feedback_up_replaces_down_and_cooked_appends(client, make_user_complete):
    u = await make_user_complete()
    mid = (await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)).json()["id"]
    await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "down"}, headers=u.headers)
    r = await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "up"}, headers=u.headers)
    assert r.status_code == 201
    assert r.json()["feedback"] == {"up": 1, "down": 0, "cooked": 0, "last_cooked_at": None}
    r = await client.post(
        f"/api/v1/meals/{mid}/feedback", json={"kind": "cooked", "comment": "great"}, headers=u.headers
    )
    assert r.json()["feedback"]["cooked"] == 1 and r.json()["feedback"]["last_cooked_at"] is not None
    r = await client.post(f"/api/v1/meals/{mid}/feedback", json={"kind": "cooked"}, headers=u.headers)
    assert r.json()["feedback"]["cooked"] == 2
    assert (await client.get(f"/api/v1/meals/{mid}", headers=u.headers)).json()["feedback"]["up"] == 1


async def test_list_filters_and_search(client, make_user_complete):
    u = await make_user_complete()
    await client.post("/api/v1/meals", json={"name": "Poha"}, headers=u.headers)
    await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)
    r = await client.get("/api/v1/meals?query=po", headers=u.headers)
    assert [m["name"] for m in r.json()["meals"]] == ["Poha"]
    r = await client.get("/api/v1/meals", headers=u.headers)
    assert [m["name"] for m in r.json()["meals"]] == ["Dal", "Poha"]
    r = await client.get("/api/v1/meals?meal_type=lunch", headers=u.headers)
    assert len(r.json()["meals"]) == 2  # fake enrichment tags the first non-breakfast slot
    r = await client.get("/api/v1/meals?meal_type=breakfast", headers=u.headers)
    assert r.json()["meals"] == []
    assert (await client.get("/api/v1/meals?source=generated", headers=u.headers)).json()["meals"] == []


async def test_patch_replaces_ingredients_and_validates_vocab(client, make_user_complete):
    u = await make_user_complete()
    mid = (await client.post("/api/v1/meals", json={"name": "Dal"}, headers=u.headers)).json()["id"]
    body = {
        "name": "Dal tadka",
        "cuisine": "North Indian",
        "diet_tags": ["vegan", "nonsense"],
        "allergens": ["mustard", "nonsense"],
        "ingredients": [
            {"name": "Toor dal", "category": "pulses"},
            {"name": "Ghee", "category": "dairy", "is_staple": True},
        ],
    }
    r = await client.patch(f"/api/v1/meals/{mid}", json=body, headers=u.headers)
    assert r.status_code == 200
    m = r.json()
    assert m["name"] == "Dal tadka" and m["cuisine"] == "north_indian"
    assert m["diet_tags"] == ["vegan"] and m["allergens"] == ["mustard"]
    assert [i["name"] for i in m["ingredients"]] == ["Toor dal", "Ghee"]


async def test_delete_and_cross_household_404(client, make_user_complete):
    a = await make_user_complete("A")
    b = await make_user_complete("B")
    mid = (await client.post("/api/v1/meals", json={"name": "Dal"}, headers=a.headers)).json()["id"]
    assert (await client.get(f"/api/v1/meals/{mid}", headers=b.headers)).status_code == 404
    assert (await client.delete(f"/api/v1/meals/{mid}", headers=b.headers)).status_code == 404
    assert (await client.delete(f"/api/v1/meals/{mid}", headers=a.headers)).status_code == 204
    assert (await client.get(f"/api/v1/meals/{mid}", headers=a.headers)).status_code == 404
