from larder.services.hashing import compute_inputs_hash


def test_hash_changes_with_pantry_but_not_feedback(planning_context_factory):
    a = planning_context_factory(pantry=["onion"])
    b = planning_context_factory(pantry=["onion", "tomato"])
    c = planning_context_factory(pantry=["onion"])
    c.library[0].feedback_up = 5
    c.members = a.members  # same member ids as a
    assert compute_inputs_hash(a) != compute_inputs_hash(b)
    assert compute_inputs_hash(a) == compute_inputs_hash(c)


def test_hash_changes_with_member_constraints_and_slots(planning_context_factory):
    a = planning_context_factory(pantry=["onion"])
    b = planning_context_factory(pantry=["onion"])
    b.members = [m.model_copy(update={"allergens": ["peanut"]}) for m in a.members]
    assert compute_inputs_hash(a) != compute_inputs_hash(b)
    c = planning_context_factory(pantry=["onion"])
    c.members = a.members
    c.slots = c.slots[:2]
    assert compute_inputs_hash(a) != compute_inputs_hash(c)


def test_unavailable_pantry_items_do_not_count(planning_context_factory):
    a = planning_context_factory(pantry=["onion"])
    b = planning_context_factory(pantry=["onion", "okra"])
    b.members = a.members
    b.pantry[1].is_available = False
    assert compute_inputs_hash(a) == compute_inputs_hash(b)
