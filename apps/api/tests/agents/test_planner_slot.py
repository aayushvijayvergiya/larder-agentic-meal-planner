from sqlalchemy import select

from larder.agents.planner.graph import run_planner
from larder.db import session as db_session_module
from larder.db.models import PlanEntry


async def test_slot_mode_replaces_one_entry_and_passes_reason(plan_setup, db_session, fake_llm):
    week = await plan_setup(mode="week")
    await run_planner(db_session_module.session_factory(), fake_llm, week)
    rows = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == week.plan_id))).scalars().all()
    before = {(e.date, e.slot_key): e.id for e in rows}
    target = next(e for e in rows if e.date == week.start_date and e.slot_key == "dinner")
    target_date, target_id = target.date, target.id

    slot = await plan_setup(
        mode="slot",
        plan_id=week.plan_id,
        target_date=target_date,
        target_slot_key="dinner",
        target_entry_id=target_id,
        swap_reason="too heavy",
    )
    out = await run_planner(db_session_module.session_factory(), fake_llm, slot)
    assert out.entries_written == 1
    db_session.expire_all()
    rows = (await db_session.execute(select(PlanEntry).where(PlanEntry.plan_id == week.plan_id))).scalars().all()
    after = {(e.date, e.slot_key): e.id for e in rows}
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {(target_date, "dinner")}
    assert "too heavy" in fake_llm.calls[-1]["user"]
