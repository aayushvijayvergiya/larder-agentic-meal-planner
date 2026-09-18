import uuid
from datetime import date

from larder.agents.planner.state import EntryDraft, IngredientDraft, NewMealDraft, PlanDraft, VariationDraft
from larder.agents.planner.validate import validate


def new_meal(name, allergens=(), tags=("vegetarian",), ings=("dal", "rice"), prep=30, cuisine="north_indian"):
    return NewMealDraft(
        name=name,
        description="d",
        cuisine=cuisine,
        meal_types=["dinner"],
        diet_tags=list(tags),
        allergens=list(allergens),
        prep_minutes=prep,
        ingredients=[IngredientDraft(name=i, category="other") for i in ings],
    )


def test_allergen_and_missing_slot_are_violations(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"])
    ctx.members[0].allergens = ["peanut"]
    ctx.requested = [(date(2026, 9, 21), "lunch"), (date(2026, 9, 21), "dinner")]
    draft = PlanDraft(
        entries=[
            EntryDraft(
                date=date(2026, 9, 21), slot_key="lunch", new_meal=new_meal("Satay", allergens=["peanut"]), reason="r"
            )
        ]
    )
    res = validate(draft, ctx, [])
    assert any("peanut" in v for v in res.violations)
    assert any("dinner" in v for v in res.violations)
    assert 0 in res.bad_entry_indexes


def test_inferred_allergen_and_unknown_meal_id(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"])
    ctx.members[0].allergens = ["dairy"]
    ctx.requested = [(date(2026, 9, 21), "dinner"), (date(2026, 9, 22), "dinner")]
    draft = PlanDraft(
        entries=[
            EntryDraft(
                date=date(2026, 9, 21),
                slot_key="dinner",
                new_meal=new_meal("Paneer bhurji", ings=("paneer", "onion")),
                reason="r",
            ),
            EntryDraft(date=date(2026, 9, 22), slot_key="dinner", existing_meal_id=uuid.uuid4(), reason="r"),
        ]
    )
    res = validate(draft, ctx, [])
    assert any("dairy" in v for v in res.violations)
    assert any("unknown meal id" in v for v in res.violations)
    assert res.bad_entry_indexes == {0, 1}


def test_existing_meal_ok_and_dislike_is_warning_only(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"])
    ctx.members[0].dislikes = ["onion"]
    ctx.requested = [(date(2026, 9, 21), "dinner")]
    draft = PlanDraft(
        entries=[EntryDraft(date=date(2026, 9, 21), slot_key="dinner", existing_meal_id=ctx.library[0].id, reason="r")]
    )
    res = validate(draft, ctx, [])
    assert res.violations == [] and res.ok
    assert any("dislikes" in w for w in res.warnings)


def test_repeat_limit_counts_fixed_entries(planning_context_factory):
    from larder.agents.planner.state import FixedEntryCtx

    ctx = planning_context_factory(pantry=["dal"])
    ctx.requested = [(date(2026, 9, d), "dinner") for d in (21, 22, 23)]
    draft = PlanDraft(
        entries=[
            EntryDraft(date=date(2026, 9, d), slot_key="dinner", new_meal=new_meal("Dal rice"), reason="r")
            for d in (21, 22, 23)
        ]
    )
    res = validate(draft, ctx, [])
    assert any("more than twice" in v for v in res.violations) and res.bad_entry_indexes == {2}

    ctx.requested = [(date(2026, 9, d), "dinner") for d in (22, 23)]
    dal_id = ctx.library[0].id
    ctx.fixed_entries = [FixedEntryCtx(date=date(2026, 9, 21), slot_key="dinner", meal_name="Dal", meal_id=dal_id)]
    draft = PlanDraft(
        entries=[
            EntryDraft(date=date(2026, 9, d), slot_key="dinner", existing_meal_id=dal_id, reason="r") for d in (22, 23)
        ]
    )
    assert any("more than twice" in v for v in validate(draft, ctx, []).violations)


def test_variations_rules_and_diet(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal"], members=2)
    ctx.members[1].diet_type = "vegan"
    ctx.requested = [(date(2026, 9, 21), "dinner")]
    e = EntryDraft(
        date=date(2026, 9, 21),
        slot_key="dinner",
        new_meal=new_meal("Paneer", tags=("vegetarian",)),
        reason="r",
        variations=[VariationDraft(member_id=uuid.uuid4(), note="x")],
    )
    res = validate(PlanDraft(entries=[e]), ctx, [])
    assert any("vegan" in v for v in res.violations) and any("unknown member" in v for v in res.violations)

    solo = planning_context_factory(pantry=["dal"])
    solo.requested = [(date(2026, 9, 21), "dinner")]
    e2 = e.model_copy(
        update={
            "new_meal": new_meal("Dal", tags=("vegan",)),
            "variations": [VariationDraft(member_id=solo.members[0].id, note="x")],
        }
    )
    assert any("single-member" in v for v in validate(PlanDraft(entries=[e2]), solo, []).violations)


def test_soft_warnings_prep_and_cuisine_streak(planning_context_factory):
    ctx = planning_context_factory(pantry=["dal", "rice"])
    ctx.requested = [(date(2026, 9, d), "dinner") for d in (21, 22, 23)]
    draft = PlanDraft(
        entries=[
            EntryDraft(date=date(2026, 9, 21), slot_key="dinner", new_meal=new_meal("A", prep=90), reason="r"),
            EntryDraft(date=date(2026, 9, 22), slot_key="dinner", new_meal=new_meal("B"), reason="r"),
            EntryDraft(date=date(2026, 9, 23), slot_key="dinner", new_meal=new_meal("C"), reason="r"),
        ]
    )
    res = validate(draft, ctx, [])
    assert res.ok
    assert any("over the 45 min limit" in w for w in res.warnings)
    assert any("three days in a row" in w for w in res.warnings)
