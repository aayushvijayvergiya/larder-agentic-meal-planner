"""Write a validated draft to the database in one transaction (LLD §8.2 persist)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.agents.planner.state import IngredientCtx, NewMealDraft, PlanDraft, PlannerInput, PlanningContext
from larder.db.models import Meal, MealIngredient, PlanEntry, PlanEntryVariation, PlanJob
from larder.services import coverage as coverage_svc
from larder.services.normalize import normalize_name


def _ingredient_ctx(meal: Meal) -> list[IngredientCtx]:
    return [
        IngredientCtx(
            name=i.name,
            normalized_name=i.normalized_name,
            category=i.category,
            is_staple=i.is_staple,
            is_optional=i.is_optional,
        )
        for i in meal.ingredients
    ]


async def _upsert_generated_meal(session: AsyncSession, household_id: UUID, draft: NewMealDraft) -> Meal:
    norm = normalize_name(draft.name)
    existing = await session.scalar(
        select(Meal)
        .where(Meal.household_id == household_id, Meal.normalized_name == norm)
        .options(selectinload(Meal.ingredients))
    )
    if existing is not None:
        return existing
    meal = Meal(
        household_id=household_id,
        name=draft.name.strip(),
        normalized_name=norm,
        description=draft.description or None,
        cuisine=draft.cuisine or None,
        meal_types=list(draft.meal_types),
        diet_tags=list(draft.diet_tags),
        allergens=list(draft.allergens),
        prep_minutes=draft.prep_minutes,
        source="generated",
        created_by=None,
        enrichment_status="complete",
        ingredients=[],
    )
    seen: set[str] = set()
    for pos, i in enumerate(draft.ingredients):
        n = normalize_name(i.name)
        if not n or n in seen:
            continue
        seen.add(n)
        meal.ingredients.append(
            MealIngredient(
                name=i.name.strip(),
                normalized_name=n,
                category=i.category,
                is_staple=i.is_staple,
                is_optional=i.is_optional,
                position=pos,
            )
        )
    session.add(meal)
    await session.flush()
    return meal


async def persist(
    session: AsyncSession,
    inp: PlannerInput,
    ctx: PlanningContext,
    draft: PlanDraft,
    *,
    attempts: int,
    used_fallback: bool,
    model_name: str,
    inputs_hash: str | None,
) -> int:
    pantry = ctx.pantry_norms
    library_meals: dict[UUID, Meal] = {}
    ids = [e.existing_meal_id for e in draft.entries if e.existing_meal_id]
    if ids:
        rows = await session.scalars(select(Meal).where(Meal.id.in_(ids)).options(selectinload(Meal.ingredients)))
        library_meals = {m.id: m for m in rows.all()}

    resolved: list[tuple[Meal, list[IngredientCtx]]] = []
    for e in draft.entries:
        if e.existing_meal_id is not None:
            meal = library_meals[e.existing_meal_id]
        else:
            assert e.new_meal is not None
            meal = await _upsert_generated_meal(session, inp.household_id, e.new_meal)
        resolved.append((meal, _ingredient_ctx(meal)))

    pairs = [(e.date, e.slot_key) for e in draft.entries]
    if pairs:
        await session.execute(
            delete(PlanEntry).where(
                PlanEntry.plan_id == inp.plan_id, tuple_(PlanEntry.date, PlanEntry.slot_key).in_(pairs)
            )
        )
    now = datetime.now(UTC)
    for e, (meal, ingredients) in zip(draft.entries, resolved, strict=True):
        cov = coverage_svc.compute(ingredients, pantry)
        entry = PlanEntry(
            plan_id=inp.plan_id,
            date=e.date,
            slot_key=e.slot_key,
            meal_id=meal.id,
            reason=e.reason or f"Uses what you have for {e.slot_key}.",
            covered_ingredients=cov.covered,
            missing_ingredients=[
                {"name": m.name, "category": m.category, "is_optional": m.is_optional} for m in cov.missing
            ],
            generated_at=now,
        )
        session.add(entry)
        await session.flush()
        for v in e.variations:
            session.add(PlanEntryVariation(plan_entry_id=entry.id, member_id=v.member_id, note=v.note))

    job = await session.get(PlanJob, inp.job_id)
    if job is not None:
        job.attempts = attempts
        job.used_fallback = used_fallback
        job.model_name = model_name
        job.inputs_hash = inputs_hash or job.inputs_hash
        job.status = "ready"
        job.finished_at = now
        job.error = None
    await session.commit()
    return len(draft.entries)
