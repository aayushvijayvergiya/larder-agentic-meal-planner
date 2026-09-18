from larder.agents.planner.vocab import diet_ok, infer_allergens, infer_diet_tags, is_staple


def test_matrix():
    assert diet_ok("vegan", ["vegan"]) and not diet_ok("vegan", ["vegetarian"])
    assert diet_ok("vegetarian", ["vegan"]) and not diet_ok("vegetarian", ["eggetarian"])
    assert diet_ok("eggetarian", ["eggetarian"]) and not diet_ok("eggetarian", ["pescatarian"])
    assert diet_ok("jain", ["jain"]) and not diet_ok("jain", ["vegan"])
    assert diet_ok("pescatarian", ["pescatarian"]) and not diet_ok("pescatarian", ["contains_meat"])
    assert diet_ok("omnivore", ["contains_meat"]) and diet_ok("other", []) and diet_ok(None, [])


def test_infer_allergens_and_tags():
    assert infer_allergens(["Paneer cubes", "wheat flour", "peanuts"]) == ["peanut", "dairy", "gluten"]
    assert infer_diet_tags(["chicken", "onion"]) == ["contains_meat"]
    assert infer_diet_tags(["prawns"]) == ["pescatarian"]
    assert infer_diet_tags(["eggs", "bread"]) == ["eggetarian"]
    assert infer_diet_tags(["paneer", "spinach"]) == ["vegetarian"]
    assert infer_diet_tags(["dal", "rice"]) == ["vegetarian", "vegan"]


def test_is_staple():
    assert is_staple("salt") and is_staple("sunflower oil") and not is_staple("paneer")
