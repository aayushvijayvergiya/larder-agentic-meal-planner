from datetime import date, timedelta

from larder.agents.planner.fallback import SIMPLE_BOWL, fallback_fill
from larder.agents.planner.shortlist import build
from larder.agents.planner.state import PlanDraft
from larder.agents.planner.validate import validate


def test_fallback_fills_everything_validly(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "onion"])
    ctx.requested = [(date(2026, 9, d), s) for d in (21, 22, 23) for s in ("lunch", "dinner")]
    sl = build(ctx, date(2026, 9, 21))
    draft = fallback_fill(None, validate(PlanDraft(entries=[]), ctx, sl), ctx, sl)
    assert len(draft.entries) == 6
    assert validate(draft, ctx, sl).violations == []
    assert sum(1 for e in draft.entries if e.existing_meal_id) == 2  # Dal used at most twice
    assert all(e.reason for e in draft.entries)


def test_fallback_keeps_good_entries_and_respects_every_diet(planning_context_factory):
    ctx = planning_context_factory(pantry=[], members=2)
    ctx.members[0].diet_type = "jain"
    ctx.members[1].allergens = ["gluten", "dairy", "peanut"]
    start = date(2026, 9, 21)
    ctx.requested = [
        (start + timedelta(days=d), s) for d in range(7) for s in ("breakfast", "lunch", "snack", "dinner")
    ]
    sl = build(ctx, start)  # Dal is not jain-safe? (diet tags lack 'jain') -> excluded
    assert sl == []
    draft = fallback_fill(None, validate(PlanDraft(entries=[]), ctx, sl), ctx, sl)
    assert len(draft.entries) == 28
    res = validate(draft, ctx, sl)
    assert res.violations == []


def test_simple_bowl_variants_are_distinct_and_safe():
    a, b = SIMPLE_BOWL("dinner", 0), SIMPLE_BOWL("dinner", 1)
    assert a.name != b.name and a.allergens == [] and "jain" in a.diet_tags
    assert len(a.ingredients) >= 2
