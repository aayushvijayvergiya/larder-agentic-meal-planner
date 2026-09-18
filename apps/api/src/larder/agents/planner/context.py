"""Loads everything the planner needs from the database (LLD §8.2 load_context)."""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.agents.planner.state import (
    FixedEntryCtx,
    IngredientCtx,
    MealCtx,
    MemberCtx,
    PantryCtx,
    PlannerInput,
    PlanningContext,
)
from larder.db.models import Household, HouseholdMember, Meal, MealPlan, PantryItem, PlanEntry, Profile
from larder.errors import not_found
from larder.schemas.common import SlotDef
from larder.services.meals import feedback_summary


def _age(dob: date | None, today: date) -> int | None:
    if dob is None:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def member_ctx(profile: Profile, today: date) -> MemberCtx:
    return MemberCtx(
        id=profile.id,
        display_name=profile.display_name or "Member",
        diet_type=profile.diet_type,
        allergens=list(profile.allergens),
        dislikes=list(profile.dislikes),
        likes=list(profile.likes),
        cuisines=list(profile.cuisines),
        medical_conditions=list(profile.medical_conditions or []),
        medical_notes=profile.medical_notes,
        goals=list(profile.goals),
        cooking_skill=profile.cooking_skill,
        max_prep_minutes=profile.max_prep_minutes,
        age=_age(profile.date_of_birth, today),
        sex=profile.sex,
        activity_level=profile.activity_level,
    )


def requested_pairs(inp: PlannerInput, slots: list[SlotDef]) -> list[tuple[date, str]]:
    keys = [s.key for s in sorted(slots, key=lambda s: s.order)]
    if inp.mode == "week":
        days = (inp.end_date - inp.start_date).days + 1
        return [(inp.start_date + timedelta(days=d), k) for d in range(days) for k in keys]
    if inp.mode == "today":
        assert inp.target_date is not None
        return [(inp.target_date, k) for k in keys]
    assert inp.target_date is not None and inp.target_slot_key is not None
    return [(inp.target_date, inp.target_slot_key)]


async def load_context(session: AsyncSession, inp: PlannerInput) -> PlanningContext:
    household = await session.scalar(
        select(Household)
        .where(Household.id == inp.household_id)
        .options(selectinload(Household.members).selectinload(HouseholdMember.profile))
    )
    if household is None:
        raise not_found("Household not found")
    slots = sorted((SlotDef(**s) for s in household.slots), key=lambda s: s.order)
    today = inp.start_date

    profiles = [m.profile for m in household.members]
    if inp.scope == "single":
        profiles = [p for p in profiles if p.id == inp.member_id]
    if not profiles:
        raise not_found("No members in scope")
    members = [member_ctx(p, today) for p in profiles]

    pantry_rows = (await session.scalars(select(PantryItem).where(PantryItem.household_id == household.id))).all()
    pantry = [
        PantryCtx(name=p.name, normalized_name=p.normalized_name, category=p.category, is_available=p.is_available)
        for p in pantry_rows
    ]

    meals = (
        await session.scalars(
            select(Meal).where(Meal.household_id == household.id).options(selectinload(Meal.ingredients))
        )
    ).all()
    summaries = await feedback_summary(session, household.id, [m.id for m in meals])
    last_used_rows = await session.execute(
        select(PlanEntry.meal_id, func.max(PlanEntry.date))
        .join(MealPlan, MealPlan.id == PlanEntry.plan_id)
        .where(MealPlan.household_id == household.id, PlanEntry.date <= today)
        .group_by(PlanEntry.meal_id)
    )
    last_used: dict[UUID, date] = {mid: d for mid, d in last_used_rows.all()}
    library = [
        MealCtx(
            id=m.id,
            name=m.name,
            description=m.description,
            cuisine=m.cuisine,
            meal_types=list(m.meal_types),
            diet_tags=list(m.diet_tags),
            allergens=list(m.allergens),
            prep_minutes=m.prep_minutes,
            source=m.source,
            ingredients=[
                IngredientCtx(
                    name=i.name,
                    normalized_name=i.normalized_name,
                    category=i.category,
                    is_staple=i.is_staple,
                    is_optional=i.is_optional,
                )
                for i in m.ingredients
            ],
            feedback_up=summaries[m.id].up,
            feedback_down=summaries[m.id].down,
            cooked_count=summaries[m.id].cooked,
            last_used_date=last_used.get(m.id),
        )
        for m in meals
    ]
    user_meals = [m for m in meals if m.source == "user"]
    max_updated = max((m.updated_at for m in user_meals), default=None)
    version = f"{len(user_meals)}:{max_updated.isoformat() if max_updated else ''}"

    recent_rows = await session.scalars(
        select(PlanEntry.meal_id)
        .join(MealPlan, MealPlan.id == PlanEntry.plan_id)
        .where(
            MealPlan.household_id == household.id,
            PlanEntry.date >= inp.start_date - timedelta(days=14),
            PlanEntry.date < inp.start_date,
        )
        .distinct()
    )
    recent_meal_ids = list(recent_rows.all())

    requested = requested_pairs(inp, slots)
    requested_set = set(requested)
    existing = (
        await session.scalars(
            select(PlanEntry).where(PlanEntry.plan_id == inp.plan_id).options(selectinload(PlanEntry.meal))
        )
    ).all()
    fixed = [
        FixedEntryCtx(date=e.date, slot_key=e.slot_key, meal_name=e.meal.name, meal_id=e.meal_id)
        for e in existing
        if (e.date, e.slot_key) not in requested_set
    ]

    return PlanningContext(
        members=members,
        pantry=pantry,
        library=library,
        slots=slots,
        recent_meal_ids=recent_meal_ids,
        fixed_entries=fixed,
        requested=requested,
        library_count_and_max_updated=version,
    )
