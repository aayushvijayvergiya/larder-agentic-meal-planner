from sqlalchemy import select

from larder.agents.planner.graph import run_planner
from larder.db import session as db_session_module
from larder.db.models import Meal, PlanEntry, PlanJob


async def test_week_plan_fills_all_slots_with_reasons(plan_setup, db_session, fake_llm):
    inp = await plan_setup(mode="week")
    out = await run_planner(db_session_module.session_factory(), fake_llm, inp)
    entries = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == inp.plan_id))).scalars().all()
    assert len(entries) == 28 and out.entries_written == 28
    assert all(e.reason for e in entries)
    assert out.used_fallback is False and out.attempts == 0
    assert any("spinach" in e.covered_ingredients for e in entries)
    assert len({(e.date, e.slot_key) for e in entries}) == 28

    job = await db_session.get(PlanJob, inp.job_id)
    assert job.status == "ready" and job.model_name == "fake" and job.inputs_hash == out.inputs_hash
    generated = (
        (
            await db_session.execute(
                select(Meal).where(Meal.household_id == inp.household_id, Meal.source == "generated")
            )
        )
        .scalars()
        .all()
    )
    assert generated, "fake bowls are stored as generated meals"
    # the draft prompt carried the compact context the LLD asks for
    draft_call = next(c for c in fake_llm.calls if c["schema"] == "PlanDraft")
    assert '"task": "planner_draft"' in draft_call["user"] and "Palak paneer" in draft_call["user"]
