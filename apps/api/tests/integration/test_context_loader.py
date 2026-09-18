import uuid
from datetime import date, timedelta

from larder.agents.planner.context import load_context
from larder.agents.planner.state import PlannerInput


async def test_load_context_week(client, make_user_complete, db_session):
    u = await make_user_complete()
    await client.post(
        "/api/v1/pantry/items", json={"items": [{"name": "spinach"}, {"name": "paneer"}]}, headers=u.headers
    )
    await client.post(
        "/api/v1/meals", json={"name": "Palak paneer", "ingredients": ["spinach", "paneer", "cream"]}, headers=u.headers
    )
    start = date.today()
    inp = PlannerInput(
        job_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        household_id=u.household.id,
        scope="single",
        member_id=u.profile.id,
        mode="week",
        start_date=start,
        end_date=start + timedelta(days=6),
    )
    ctx = await load_context(db_session, inp)
    assert len(ctx.requested) == 28 and ctx.requested[0] == (start, "breakfast")
    assert len(ctx.members) == 1 and ctx.members[0].display_name == "Priya"
    assert len(ctx.library) == 1 and ctx.library[0].name == "Palak paneer"
    assert {p.normalized_name for p in ctx.pantry} == {"spinach", "paneer"}
    assert ctx.fixed_entries == [] and ctx.recent_meal_ids == []
    assert ctx.library_count_and_max_updated.startswith("1:")


async def test_load_context_today_and_slot_modes(client, make_user_complete, db_session):
    u = await make_user_complete()
    start = date.today()
    base = dict(
        job_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        household_id=u.household.id,
        scope="single",
        member_id=u.profile.id,
        start_date=start,
        end_date=start + timedelta(days=6),
    )
    today = await load_context(db_session, PlannerInput(mode="today", target_date=start + timedelta(days=1), **base))
    assert today.requested == [(start + timedelta(days=1), k) for k in ("breakfast", "lunch", "snack", "dinner")]
    slot = await load_context(
        db_session, PlannerInput(mode="slot", target_date=start, target_slot_key="dinner", **base)
    )
    assert slot.requested == [(start, "dinner")]


async def test_family_scope_loads_all_members(client, make_user_complete, db_session):
    from larder.services.households import generate_invite

    owner = await make_user_complete("Priya")
    joiner = await make_user_complete("Aarav")
    inv = await generate_invite(db_session, owner.household, owner.profile.id)
    await db_session.commit()
    await client.post("/api/v1/households/join", json={"code": inv.code}, headers=joiner.headers)
    start = date.today()
    inp = PlannerInput(
        job_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        household_id=owner.household.id,
        scope="family",
        mode="week",
        start_date=start,
        end_date=start + timedelta(days=6),
    )
    ctx = await load_context(db_session, inp)
    assert {m.display_name for m in ctx.members} == {"Priya", "Aarav"}
