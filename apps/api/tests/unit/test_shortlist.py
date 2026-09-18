import uuid
from datetime import date, timedelta

from larder.agents.planner.shortlist import build, hard_conflict


def test_allergen_conflict_excluded(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"])
    ctx.members[0].allergens = ["dairy"]
    ctx.library[0].allergens = ["dairy"]
    assert hard_conflict(ctx.library[0], ctx.members) is not None
    assert build(ctx, date.today()) == []


def test_inferred_allergen_and_diet_conflicts(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"])
    ctx.members[0].allergens = ["dairy"]
    ctx.library[0].ingredients[1].name = "paneer"  # allergen inferred from the ingredient name
    assert "dairy" in hard_conflict(ctx.library[0], ctx.members)
    ctx = planning_context_factory(pantry=["dal", "onion"])
    ctx.members[0].diet_type = "jain"
    assert "jain" in hard_conflict(ctx.library[0], ctx.members)
    ctx = planning_context_factory(pantry=["dal", "onion"])
    ctx.members[0].medical_conditions = [{"name": "lactose intolerance"}]
    ctx.library[0].allergens = ["dairy"]
    assert "must avoid" in hard_conflict(ctx.library[0], ctx.members)


def test_scoring_prefers_coverage_and_penalises_recent(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"])
    m = ctx.library[0].model_copy(
        update={"id": uuid.uuid4(), "name": "Recent dal", "last_used_date": date.today() - timedelta(days=2)}
    )
    ctx.library.append(m)
    ranked = build(ctx, date.today())
    assert [c.meal.name for c in ranked] == ["Dal", "Recent dal"]
    assert ranked[0].coverage == 1.0 and ranked[1].score < ranked[0].score
    assert ranked[0].covered == ["dal", "onion"] and ranked[0].missing == []


def test_low_coverage_generated_meals_are_dropped_but_user_meals_kept(planning_context_factory):
    ctx = planning_context_factory(pantry=[])
    generated = ctx.library[0].model_copy(update={"id": uuid.uuid4(), "name": "Gen", "source": "generated"})
    ctx.library.append(generated)
    assert [c.meal.name for c in build(ctx, date.today())] == ["Dal"]
