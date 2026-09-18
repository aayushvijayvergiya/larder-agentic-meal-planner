from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

import larder.services.scheduler as sched
from larder.db.models import MealPlan, PlanJob

HDR = {"X-Scheduler-Secret": "test-scheduler"}
TICK = "/api/v1/internal/scheduler/tick"


def _at(monkeypatch, y, m, d, hh, mm):
    monkeypatch.setattr(sched, "utcnow", lambda: datetime(y, m, d, hh, mm, tzinfo=UTC))


async def _plans(db_session, household_id):
    rows = (
        (
            await db_session.execute(
                select(MealPlan)
                .where(MealPlan.household_id == household_id, MealPlan.status == "active")
                .order_by(MealPlan.start_date)
            )
        )
        .scalars()
        .all()
    )
    return [(p.start_date, p.end_date) for p in rows]


async def test_bad_or_missing_secret_forbidden(client):
    assert (await client.post(TICK, headers={"X-Scheduler-Secret": "no"})).status_code == 403
    assert (await client.post(TICK)).status_code == 403


async def test_daily_tick_creates_week_when_no_plan_then_skips_when_unchanged(
    client, make_user_complete, monkeypatch, db_session
):
    u = await make_user_complete()  # tz Asia/Kolkata: 06:00 IST == 00:30 UTC
    await client.post("/api/v1/pantry/items", json={"items": [{"name": "rice"}, {"name": "dal"}]}, headers=u.headers)
    _at(monkeypatch, 2026, 9, 18, 1, 0)  # Friday 06:30 IST
    r = await client.post(TICK, headers=HDR)
    assert r.status_code == 200, r.text
    assert len(r.json()["daily_enqueued"]) == 1 and r.json()["weekly_enqueued"] == []
    assert await _plans(db_session, u.household.id) == [(date(2026, 9, 18), date(2026, 9, 24))]

    r = await client.post(TICK, headers=HDR)  # same day again: idempotent
    assert r.json()["daily_enqueued"] == [] and r.json()["skipped"] >= 1

    _at(monkeypatch, 2026, 9, 19, 1, 0)  # next day, nothing changed
    r = await client.post(TICK, headers=HDR)
    assert r.json()["daily_enqueued"] == []

    await client.post("/api/v1/pantry/items", json={"items": [{"name": "okra"}]}, headers=u.headers)
    _at(monkeypatch, 2026, 9, 20, 1, 0)  # pantry changed -> today job
    r = await client.post(TICK, headers=HDR)
    assert len(r.json()["daily_enqueued"]) == 1
    db_session.expire_all()
    jobs = (await db_session.execute(select(PlanJob).order_by(PlanJob.created_at))).scalars().all()
    assert [j.mode for j in jobs] == ["week", "today"]
    assert jobs[-1].origin == "scheduler" and jobs[-1].target_date == date(2026, 9, 20) and jobs[-1].status == "ready"


async def test_weekly_tick_idempotent_and_daily_gap_fills(client, make_user_complete, monkeypatch, db_session):
    u = await make_user_complete()
    _at(monkeypatch, 2026, 9, 20, 13, 0)  # Sunday 18:30 IST
    a = (await client.post(TICK, headers=HDR)).json()
    b = (await client.post(TICK, headers=HDR)).json()
    assert len(a["weekly_enqueued"]) == 1 and b["weekly_enqueued"] == []
    # daily step ran after weekly in tick `a`: no plan contained Sunday, so a one-day gap-fill plan was created
    assert len(a["daily_enqueued"]) == 1 and b["daily_enqueued"] == []
    assert await _plans(db_session, u.household.id) == [
        (date(2026, 9, 20), date(2026, 9, 20)),
        (date(2026, 9, 21), date(2026, 9, 27)),
    ]


async def test_household_schedule_and_timezone_are_respected(client, make_user_complete, monkeypatch):
    u = await make_user_complete()
    body = {
        "timezone": "Europe/London",
        "weekly_refresh_day": 2,
        "weekly_refresh_time": "20:00:00",
        "daily_refresh_time": "07:00:00",
    }
    await client.patch(f"/api/v1/households/{u.household.id}", json=body, headers=u.headers)
    _at(monkeypatch, 2026, 9, 16, 5, 30)  # Wednesday 06:30 London (BST): nothing due
    r = (await client.post(TICK, headers=HDR)).json()
    assert r["weekly_enqueued"] == [] and r["daily_enqueued"] == [] and r["skipped"] == 1
    _at(monkeypatch, 2026, 9, 16, 19, 30)  # Wednesday 20:30 London: weekly + daily due
    r = (await client.post(TICK, headers=HDR)).json()
    assert len(r["weekly_enqueued"]) == 1 and len(r["daily_enqueued"]) == 1


async def test_cleanup_deletes_old_superseded_plans(client, make_user_complete, monkeypatch, db_session):
    u = await make_user_complete()
    old = MealPlan(
        household_id=u.household.id,
        scope="single",
        member_id=u.profile.id,
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 11),
        status="superseded",
    )
    recent = MealPlan(
        household_id=u.household.id,
        scope="single",
        member_id=u.profile.id,
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() - timedelta(days=4),
        status="superseded",
    )
    db_session.add_all([old, recent])
    await db_session.commit()
    _at(monkeypatch, 2026, 9, 18, 1, 0)
    r = (await client.post(TICK, headers=HDR)).json()
    assert r["cleaned_plans"] == 1
    db_session.expire_all()
    remaining = (await db_session.execute(select(MealPlan).where(MealPlan.status == "superseded"))).scalars().all()
    assert [p.start_date for p in remaining] == [recent.start_date]
