"""Scheduler tick: weekly and daily refresh decisions per household (LLD §7.5)."""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.agents.planner.context import load_context
from larder.agents.planner.state import PlannerInput
from larder.db.models import Household, HouseholdMember, MealPlan, PlanJob, RefreshRun
from larder.errors import ApiError
from larder.jobs import runner
from larder.llm.base import LLM
from larder.schemas.internal import TickReport
from larder.services import plans as plans_svc
from larder.services.hashing import compute_inputs_hash
from larder.services.households import active_scopes

log = logging.getLogger("larder.scheduler")


def utcnow() -> datetime:
    return datetime.now(UTC)


def weekly_due(household, local_now: datetime) -> str | None:
    if local_now.weekday() != household.weekly_refresh_day:
        return None
    if local_now.time() < household.weekly_refresh_time:
        return None
    iso = local_now.date().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def daily_due(household, local_now: datetime) -> str | None:
    if local_now.time() < household.daily_refresh_time:
        return None
    return local_now.date().isoformat()


async def _claim_run(session: AsyncSession, household_id: uuid.UUID, kind: str, period_key: str) -> RefreshRun | None:
    """Insert the idempotency row; returns it only when this tick won the claim."""
    stmt = (
        insert(RefreshRun)
        .values(household_id=household_id, kind=kind, period_key=period_key, result={})
        .on_conflict_do_nothing(constraint="uq_refresh_runs_period")
        .returning(RefreshRun.id)
    )
    run_id = await session.scalar(stmt)
    await session.commit()
    return await session.get(RefreshRun, run_id) if run_id else None


async def _latest_ready_hash(session: AsyncSession, plan_id: uuid.UUID) -> str | None:
    job = await session.scalar(
        select(PlanJob)
        .where(PlanJob.plan_id == plan_id, PlanJob.status == "ready")
        .order_by(PlanJob.finished_at.desc().nulls_last(), PlanJob.created_at.desc())
    )
    return job.inputs_hash if job else None


async def _current_hash(session: AsyncSession, plan: MealPlan, today: date) -> str:
    inp = PlannerInput(
        job_id=uuid.uuid4(),
        plan_id=plan.id,
        household_id=plan.household_id,
        scope=plan.scope,
        member_id=plan.member_id,
        mode="today",
        start_date=plan.start_date,
        end_date=plan.end_date,
        target_date=today,
    )
    return compute_inputs_hash(await load_context(session, inp))


async def _weekly(session, household, local_today: date, background, llm, report: TickReport) -> dict:
    result: dict = {"enqueued": [], "errors": []}
    start = local_today + timedelta(days=1)
    for scope, member_id in active_scopes(household):
        try:
            job_id, _ = await plans_svc.request_generation(
                session,
                household=household,
                scope=scope,
                member_id=member_id,
                mode="week",
                on_date=start,
                origin="scheduler",
                background=background,
                llm=llm,
            )
            result["enqueued"].append(str(job_id))
            report.weekly_enqueued.append(job_id)
        except ApiError as exc:
            result["errors"].append(exc.message)
    return result


async def _daily(session, household, local_today: date, background, llm, report: TickReport) -> dict:
    result: dict = {"enqueued": [], "skipped": [], "errors": []}
    for scope, member_id in active_scopes(household):
        try:
            plan = await plans_svc.active_plan_for(session, household.id, scope, member_id, local_today)
            if plan is None:
                nxt = await plans_svc.next_plan_after(session, household.id, scope, member_id, local_today)
                end = local_today + timedelta(days=6)
                if nxt is not None:
                    end = min(end, nxt.start_date - timedelta(days=1))
                job_id, _ = await plans_svc.request_generation(
                    session,
                    household=household,
                    scope=scope,
                    member_id=member_id,
                    mode="week",
                    on_date=local_today,
                    origin="scheduler",
                    background=background,
                    llm=llm,
                    end_date=end,
                )
                result["enqueued"].append(str(job_id))
                report.daily_enqueued.append(job_id)
                continue
            if await plans_svc.has_active_job(session, plan.id):
                result["skipped"].append({"scope": scope, "reason": "job_running"})
                continue
            previous = await _latest_ready_hash(session, plan.id)
            if previous is None:
                job = await plans_svc.create_job(session, plan, "week", "scheduler")
                await session.commit()
                await runner.enqueue(job.id, background, llm)
                result["enqueued"].append(str(job.id))
                report.daily_enqueued.append(job.id)
                continue
            if await _current_hash(session, plan, local_today) == previous:
                result["skipped"].append({"scope": scope, "reason": "unchanged"})
                continue
            job = await plans_svc.create_job(session, plan, "today", "scheduler", target_date=local_today)
            await session.commit()
            await runner.enqueue(job.id, background, llm)
            result["enqueued"].append(str(job.id))
            report.daily_enqueued.append(job.id)
        except ApiError as exc:
            result["errors"].append(exc.message)
    return result


async def _cleanup(session: AsyncSession, today: date, history_weeks: int) -> int:
    cutoff = today - timedelta(days=history_weeks * 7)
    res = await session.execute(delete(MealPlan).where(MealPlan.status == "superseded", MealPlan.end_date < cutoff))
    await session.commit()
    return res.rowcount or 0


async def run_tick(
    session: AsyncSession, now_utc: datetime, background: BackgroundTasks, llm: LLM, history_weeks: int = 8
) -> TickReport:
    report = TickReport(ran_at=now_utc)
    households = (
        await session.scalars(
            select(Household).options(selectinload(Household.members).selectinload(HouseholdMember.profile))
        )
    ).all()
    for h in households:
        report.households_checked += 1
        try:
            local = now_utc.astimezone(ZoneInfo(h.timezone))
        except Exception:  # noqa: BLE001
            local = now_utc
        did_anything = False
        key = weekly_due(h, local)
        if key:
            run = await _claim_run(session, h.id, "weekly", key)
            if run is not None:
                run.result = await _weekly(session, h, local.date(), background, llm, report)
                await session.commit()
                did_anything = bool(run.result["enqueued"])
        key = daily_due(h, local)
        if key:
            run = await _claim_run(session, h.id, "daily", key)
            if run is not None:
                run.result = await _daily(session, h, local.date(), background, llm, report)
                await session.commit()
                did_anything = did_anything or bool(run.result["enqueued"])
        if not did_anything:
            report.skipped += 1
    report.cleaned_plans = await _cleanup(session, now_utc.date(), history_weeks)
    log.info(
        "tick: %s households, %s weekly, %s daily, %s cleaned",
        report.households_checked,
        len(report.weekly_enqueued),
        len(report.daily_enqueued),
        report.cleaned_plans,
    )
    return report
