from sqlalchemy import select

from larder.agents.planner.graph import run_planner
from larder.agents.planner.state import EntryDraft, IngredientDraft, NewMealDraft, PlanDraft
from larder.db import session as db_session_module
from larder.db.models import Meal, PlanEntry
from larder.llm.base import LLMError


def bad_draft(start):
    return PlanDraft(
        entries=[
            EntryDraft(
                date=start,
                slot_key="dinner",
                new_meal=NewMealDraft(
                    name="Paneer butter masala",
                    cuisine="north_indian",
                    meal_types=["dinner"],
                    diet_tags=["vegetarian"],
                    allergens=["dairy"],
                    prep_minutes=40,
                    ingredients=[
                        IngredientDraft(name="paneer", category="dairy"),
                        IngredientDraft(name="butter", category="dairy"),
                    ],
                ),
                reason="rich",
            )
        ]
    )


async def test_repair_loop_fixes_allergen_violation(plan_setup, fake_llm, db_session, make_user_complete):
    u = await make_user_complete("Priya", allergens=["dairy"])
    inp = await plan_setup(mode="week", user=u)
    fake_llm.script_structured(PlanDraft, [bad_draft(inp.start_date)])
    out = await run_planner(db_session_module.session_factory(), fake_llm, inp)
    assert out.attempts == 1 and out.used_fallback is False and out.entries_written == 28
    repair_call = [c for c in fake_llm.calls if c["schema"] == "PlanDraft"][1]
    assert "planner_repair" in repair_call["user"] and "dairy" in repair_call["system"]
    meals = (await db_session.execute(select(Meal).where(Meal.household_id == u.household.id))).scalars().all()
    assert all("dairy" not in m.allergens for m in meals if m.source == "generated")
    entries = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == inp.plan_id))).scalars().all()
    assert len(entries) == 28


async def test_llm_error_on_draft_is_repaired(plan_setup, fake_llm):
    inp = await plan_setup(mode="week")
    fake_llm.fail_next(LLMError("timeout"))
    out = await run_planner(db_session_module.session_factory(), fake_llm, inp)
    assert out.attempts == 1 and out.used_fallback is False and out.entries_written == 28
