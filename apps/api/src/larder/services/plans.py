"""Plan lifecycle: current plan, generation requests, swaps, jobs (LLD §6.8)."""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.db.models import Household, Meal, MealFeedback, MealPlan, PlanEntry, PlanJob
from larder.errors import job_running, not_found, validation
from larder.jobs import runner
from larder.llm.base import LLM
from larder.schemas.common import SlotDef
from larder.schemas.meals import MealOut
from larder.schemas.plans import (
    ActiveJobOut,
    CoverageOut,
    CurrentPlanOut,
    MissingIngredientOut,
    PlanDayOut,
    PlanEntryOut,
    PlanOut,
    UnusedItemOut,
    VariationOut,
)
from larder.services.meals import feedback_summary

ACTIVE_JOB_STATUSES = ("queued", "running")


def household_today(household: Household) -> date:
    return datetime.now(ZoneInfo(household.timezone)).date()


async def active_plan_for(
    session: AsyncSession, household_id: uuid.UUID, scope: str, member_id: uuid.UUID | None, on_date: date
) -> MealPlan | None:
    stmt = select(MealPlan).where(
        MealPlan.household_id == household_id,
        MealPlan.scope == scope,
        MealPlan.status == "active",
        MealPlan.start_date <= on_date,
        MealPlan.end_date >= on_date,
    )
    stmt = stmt.where(MealPlan.member_id == member_id) if member_id else stmt.where(MealPlan.member_id.is_(None))
    return await session.scalar(stmt.order_by(MealPlan.created_at.desc()))


async def next_plan_after(
    session: AsyncSession, household_id: uuid.UUID, scope: str, member_id: uuid.UUID | None, after: date
) -> MealPlan | None:
    stmt = select(MealPlan).where(
        MealPlan.household_id == household_id,
        MealPlan.scope == scope,
        MealPlan.status == "active",
        MealPlan.start_date > after,
    )
    stmt = stmt.where(MealPlan.member_id == member_id) if member_id else stmt.where(MealPlan.member_id.is_(None))
    return await session.scalar(stmt.order_by(MealPlan.start_date.asc()))


async def active_job_for(session: AsyncSession, plan_id: uuid.UUID) -> PlanJob | None:
    return await session.scalar(
        select(PlanJob)
        .where(PlanJob.plan_id == plan_id, PlanJob.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(PlanJob.created_at.desc())
    )


async def has_active_job(session: AsyncSession, plan_id: uuid.UUID) -> bool:
    return await active_job_for(session, plan_id) is not None


def validate_scope(household: Household, scope: str) -> None:
    if scope == "family" and len(household.members) < 2:
        raise validation("Family view needs at least two members", field="scope")


async def create_plan(
    session: AsyncSession,
    household_id: uuid.UUID,
    scope: str,
    member_id: uuid.UUID | None,
    start: date,
    end: date,
    *,
    supersede_overlaps: bool = True,
) -> MealPlan:
    if supersede_overlaps:
        stmt = (
            update(MealPlan)
            .where(
                MealPlan.household_id == household_id,
                MealPlan.scope == scope,
                MealPlan.status == "active",
                MealPlan.start_date <= end,
                MealPlan.end_date >= start,
            )
            .values(status="superseded")
        )
        stmt = stmt.where(MealPlan.member_id == member_id) if member_id else stmt.where(MealPlan.member_id.is_(None))
        await session.execute(stmt)
    plan = MealPlan(household_id=household_id, scope=scope, member_id=member_id, start_date=start, end_date=end)
    session.add(plan)
    await session.flush()
    return plan


async def create_job(
    session: AsyncSession,
    plan: MealPlan,
    mode: str,
    origin: str,
    *,
    target_date: date | None = None,
    target_slot_key: str | None = None,
    target_entry_id: uuid.UUID | None = None,
    swap_reason: str | None = None,
) -> PlanJob:
    if await has_active_job(session, plan.id):
        raise job_running()
    job = PlanJob(
        plan_id=plan.id,
        mode=mode,
        origin=origin,
        target_date=target_date,
        target_slot_key=target_slot_key,
        target_entry_id=target_entry_id,
        swap_reason=swap_reason,
    )
    session.add(job)
    await session.flush()
    return job


async def request_generation(
    session: AsyncSession,
    *,
    household: Household,
    scope: str,
    member_id: uuid.UUID | None,
    mode: str,
    on_date: date | None,
    origin: str,
    background: BackgroundTasks,
    llm: LLM,
    end_date: date | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Creates the plan (week) or targets the existing one (today), records the job and enqueues it."""
    on_date = on_date or household_today(household)
    if mode == "week":
        plan = await create_plan(
            session, household.id, scope, member_id, on_date, end_date or on_date + timedelta(days=6)
        )
        job = await create_job(session, plan, "week", origin)
    else:
        plan = await active_plan_for(session, household.id, scope, member_id, on_date)
        if plan is None:
            raise not_found("No plan covers that date yet; generate a week first")
        job = await create_job(session, plan, "today", origin, target_date=on_date)
    await session.commit()
    await runner.enqueue(job.id, background, llm)
    return job.id, plan.id


async def request_swap(
    session: AsyncSession,
    *,
    household: Household,
    plan_id: uuid.UUID,
    entry_id: uuid.UUID,
    reason: str | None,
    background: BackgroundTasks,
    llm: LLM,
) -> uuid.UUID:
    plan = await session.get(MealPlan, plan_id)
    if plan is None or plan.household_id != household.id:
        raise not_found("Plan not found")
    entry = await session.get(PlanEntry, entry_id)
    if entry is None or entry.plan_id != plan.id:
        raise not_found("Plan entry not found")
    job = await create_job(
        session,
        plan,
        "slot",
        "user",
        target_date=entry.date,
        target_slot_key=entry.slot_key,
        target_entry_id=entry.id,
        swap_reason=reason,
    )
    await session.commit()
    await runner.enqueue(job.id, background, llm)
    return job.id


async def enqueue_first_plan(
    session: AsyncSession, profile, household: Household, background: BackgroundTasks, llm: LLM
):
    job_id, _ = await request_generation(
        session,
        household=household,
        scope="single",
        member_id=profile.id,
        mode="week",
        on_date=None,
        origin="onboarding",
        background=background,
        llm=llm,
    )
    return job_id


async def get_job(session: AsyncSession, household: Household, job_id: uuid.UUID) -> PlanJob:
    job = await session.scalar(
        select(PlanJob)
        .join(MealPlan, MealPlan.id == PlanJob.plan_id)
        .where(PlanJob.id == job_id, MealPlan.household_id == household.id)
    )
    if job is None:
        raise not_found("Job not found")
    return job


async def _my_feedback(session: AsyncSession, member_id: uuid.UUID, meal_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not meal_ids:
        return {}
    rows = await session.execute(
        select(MealFeedback.meal_id, MealFeedback.kind)
        .where(
            MealFeedback.member_id == member_id,
            MealFeedback.meal_id.in_(meal_ids),
            MealFeedback.kind.in_(["up", "down"]),
        )
        .order_by(MealFeedback.created_at.asc())
    )
    out: dict[uuid.UUID, str] = {}
    for meal_id, kind in rows.all():
        out[meal_id] = kind
    return out


async def get_current_plan(
    session: AsyncSession, household: Household, member_id: uuid.UUID, scope: str, on_date: date | None
) -> CurrentPlanOut:
    on_date = on_date or household_today(household)
    plan_member = member_id if scope == "single" else None
    plan = await active_plan_for(session, household.id, scope, plan_member, on_date)
    if plan is None:
        return CurrentPlanOut(plan=None, active_job=None)
    active = await active_job_for(session, plan.id)
    active_out = (
        ActiveJobOut(id=active.id, mode=active.mode, status=active.status, created_at=active.created_at)
        if active
        else None
    )

    entries = (
        await session.scalars(
            select(PlanEntry)
            .where(PlanEntry.plan_id == plan.id)
            .options(selectinload(PlanEntry.meal).selectinload(Meal.ingredients), selectinload(PlanEntry.variations))
            .order_by(PlanEntry.date)
        )
    ).all()
    if not entries:
        return CurrentPlanOut(plan=None, active_job=active_out)

    slots = sorted((SlotDef(**s) for s in household.slots), key=lambda s: s.order)
    slot_order = {s.key: s.order for s in slots}
    slot_label = {s.key: s.label for s in slots}
    names = {m.user_id: (m.profile.display_name if m.profile else None) for m in household.members}
    meal_ids = list({e.meal_id for e in entries})
    summaries = await feedback_summary(session, household.id, meal_ids)
    mine = await _my_feedback(session, member_id, meal_ids)

    on_hand = needed = 0
    by_date: dict[date, list[PlanEntryOut]] = {}
    for e in entries:
        missing = [MissingIngredientOut(**m) for m in e.missing_ingredients]
        on_hand += len(e.covered_ingredients)
        needed += len(e.covered_ingredients) + sum(1 for m in missing if not m.is_optional)
        by_date.setdefault(e.date, []).append(
            PlanEntryOut(
                id=e.id,
                date=e.date,
                slot_key=e.slot_key,
                slot_label=slot_label.get(e.slot_key, e.slot_key.title()),
                meal=MealOut.from_model(e.meal, summaries.get(e.meal_id)),
                reason=e.reason,
                covered_ingredients=list(e.covered_ingredients),
                missing_ingredients=missing,
                variations=[
                    VariationOut(member_id=v.member_id, display_name=names.get(v.member_id), note=v.note)
                    for v in e.variations
                ],
                my_feedback=mine.get(e.meal_id),
                cooked_count=summaries[e.meal_id].cooked if e.meal_id in summaries else 0,
            )
        )
    days: list[PlanDayOut] = []
    d = plan.start_date
    while d <= plan.end_date:
        days.append(
            PlanDayOut(date=d, entries=sorted(by_date.get(d, []), key=lambda x: slot_order.get(x.slot_key, 99)))
        )
        d += timedelta(days=1)

    from larder.services.unused import unused_pantry_items

    unused = await unused_pantry_items(session, household.id, entries, on_date)
    return CurrentPlanOut(
        plan=PlanOut(
            id=plan.id,
            scope=plan.scope,
            member_id=plan.member_id,
            start_date=plan.start_date,
            end_date=plan.end_date,
            days=days,
            coverage=CoverageOut(on_hand=on_hand, needed=needed),
            unused_pantry=[UnusedItemOut(**u) for u in unused],
        ),
        active_job=active_out,
    )
