from sqlalchemy import select

from larder.agents.planner.graph import run_planner
from larder.db import session as db_session_module
from larder.db.models import PlanEntry


async def _ids(db_session, plan_id):
    rows = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == plan_id))).scalars().all()
    return {(e.date, e.slot_key): e.id for e in rows}


async def test_today_mode_only_touches_target_date(plan_setup, db_session, fake_llm):
    week = await plan_setup(mode="week")
    await run_planner(db_session_module.session_factory(), fake_llm, week)
    before = await _ids(db_session, week.plan_id)
    assert len(before) == 28

    today = await plan_setup(mode="today", plan_id=week.plan_id, target_date=week.start_date)
    out = await run_planner(db_session_module.session_factory(), fake_llm, today)
    assert out.entries_written == 4
    db_session.expire_all()
    after = await _ids(db_session, week.plan_id)
    assert len(after) == 28
    changed = {k for k in before if before[k] != after.get(k)}
    assert changed and all(k[0] == week.start_date for k in changed) and len(changed) == 4

    draft_call = [c for c in fake_llm.calls if c["schema"] == "PlanDraft"][-1]
    assert '"mode": "today"' in draft_call["user"] and '"fixed_entries": [{' in draft_call["user"]
