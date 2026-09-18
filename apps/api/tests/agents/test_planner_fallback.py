from sqlalchemy import select

from larder.agents.planner.graph import run_planner
from larder.agents.planner.state import PlanDraft
from larder.db import session as db_session_module
from larder.db.models import PlanEntry, PlanJob
from tests.agents.test_planner_repair import bad_draft


async def test_three_bad_drafts_trigger_fallback(plan_setup, fake_llm, db_session, make_user_complete):
    u = await make_user_complete("Priya", allergens=["dairy"])
    inp = await plan_setup(mode="week", user=u)
    fake_llm.script_structured(PlanDraft, [bad_draft(inp.start_date)] * 3)
    out = await run_planner(db_session_module.session_factory(), fake_llm, inp)
    assert out.used_fallback is True and out.attempts == 2 and out.entries_written == 28
    entries = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == inp.plan_id))).scalars().all()
    assert len(entries) == 28 and all(e.reason for e in entries)
    job = await db_session.get(PlanJob, inp.job_id)
    assert job.status == "ready" and job.used_fallback is True and job.attempts == 2
    assert sum(1 for c in fake_llm.calls if c["schema"] == "PlanDraft") == 3
