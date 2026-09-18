import pytest
import sqlalchemy.exc
from sqlalchemy import text


async def test_all_tables_exist(db_session):
    rows = await db_session.execute(
        text("select table_name from information_schema.tables where table_schema='public'")
    )
    names = {r[0] for r in rows}
    expected = {
        "profiles",
        "households",
        "household_members",
        "household_invites",
        "pantry_items",
        "meals",
        "meal_ingredients",
        "meal_plans",
        "plan_entries",
        "plan_entry_variations",
        "plan_jobs",
        "meal_feedback",
        "refresh_runs",
    }
    assert expected <= names


async def test_one_household_per_user(db_session, make_user_complete):
    from larder.db.models import Household, HouseholdMember

    user = await make_user_complete()
    other = Household(
        name="x",
        owner_id=user.profile.id,
        timezone="Asia/Kolkata",
        slots=[{"key": "dinner", "label": "Dinner", "order": 1}],
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(HouseholdMember(household_id=other.id, user_id=user.profile.id, role="member"))
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()
