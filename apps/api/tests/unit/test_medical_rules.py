from larder.agents.planner.medical_rules import rules_for


def test_celiac_and_diabetes():
    r = rules_for([{"name": "Celiac disease"}, {"name": "Type 2 Diabetes", "notes": ""}])
    assert "gluten" in r.hard_allergens
    assert "sugar" in r.avoid_tokens and "jaggery" in r.avoid_tokens
    assert len(r.notes) == 2


def test_no_conditions_and_unknown_condition():
    assert rules_for([]).hard_allergens == set()
    assert rules_for([{"name": "migraine"}]).avoid_tokens == set()
    assert rules_for(None).notes == []


def test_lactose_and_string_entries():
    r = rules_for(["lactose intolerance"])
    assert r.hard_allergens == {"dairy"}
