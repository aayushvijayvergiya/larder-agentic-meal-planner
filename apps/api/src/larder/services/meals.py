"""Meal library and feedback (LLD §6.7)."""

import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.agents.categorize.keyword_map import keyword_category
from larder.agents.enrichment.enrich import enrich_meal
from larder.agents.enrichment.schemas import IngredientDraft, MealEnrichment
from larder.agents.planner.vocab import ALLERGENS, DIET_TAGS, is_staple
from larder.db.models import Household, Meal, MealFeedback, MealIngredient, MealPlan, PlanEntry
from larder.errors import conflict, forbidden, not_found, validation
from larder.llm.base import LLM, LLMError
from larder.schemas.meals import FeedbackSummary, MealCreate, MealPatch
from larder.services.normalize import normalize_name, slugify

log = logging.getLogger("larder.meals")


def _meal_query(household_id: uuid.UUID):
    return select(Meal).where(Meal.household_id == household_id).options(selectinload(Meal.ingredients))


async def get_meal(session: AsyncSession, household_id: uuid.UUID, meal_id: uuid.UUID) -> Meal:
    meal = await session.scalar(_meal_query(household_id).where(Meal.id == meal_id))
    if meal is None:
        raise not_found("Meal not found")
    return meal


async def list_meals(
    session: AsyncSession,
    household_id: uuid.UUID,
    query: str | None = None,
    meal_type: str | None = None,
    source: str = "user",
) -> list[Meal]:
    stmt = _meal_query(household_id)
    if query:
        stmt = stmt.where(Meal.name.ilike(f"%{query.strip()}%"))
    if meal_type:
        stmt = stmt.where(Meal.meal_types.any(meal_type) | Meal.meal_types.any("any"))
    if source in ("user", "generated"):
        stmt = stmt.where(Meal.source == source)
    stmt = stmt.order_by(Meal.name).limit(500)
    return list((await session.scalars(stmt)).all())


async def _replace_ingredients(session: AsyncSession, meal: Meal, drafts: list[IngredientDraft]) -> None:
    """Delete the old rows before inserting the new ones so same-named ingredients never collide."""
    meal.ingredients = []  # delete-orphan cascade removes the old rows on flush
    await session.flush()
    seen: set[str] = set()
    position = 0
    for d in drafts:
        norm = normalize_name(d.name)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        meal.ingredients.append(
            MealIngredient(
                name=d.name.strip(),
                normalized_name=norm,
                category=d.category,
                is_staple=d.is_staple,
                is_optional=d.is_optional,
                position=position,
            )
        )
        position += 1
    await session.flush()


async def _apply_enrichment(session: AsyncSession, meal: Meal, enr: MealEnrichment, keep_description: bool) -> None:
    if not keep_description or not meal.description:
        meal.description = enr.description or meal.description
    meal.cuisine = enr.cuisine
    meal.meal_types = enr.meal_types
    meal.diet_tags = enr.diet_tags
    meal.allergens = enr.allergens
    meal.prep_minutes = enr.prep_minutes
    await _replace_ingredients(session, meal, enr.ingredients)
    meal.enrichment_status = "complete"


def _raw_ingredients(names: list[str] | None) -> list[IngredientDraft]:
    out: list[IngredientDraft] = []
    for n in names or []:
        norm = normalize_name(n)
        if norm:
            out.append(IngredientDraft(name=n, category=keyword_category(norm) or "other", is_staple=is_staple(n)))
    return out


async def _run_enrichment(
    session: AsyncSession, llm: LLM, household: Household, meal: Meal, ingredient_names: list[str] | None
) -> None:
    slot_keys = [s["key"] for s in household.slots]
    try:
        enr = await enrich_meal(
            llm,
            name=meal.name,
            description=meal.description,
            ingredients=ingredient_names,
            instructions=meal.instructions,
            slot_keys=slot_keys,
        )
    except LLMError as exc:
        log.warning("enrichment failed for meal %s: %s", meal.name, exc)
        meal.enrichment_status = "failed"
        if not meal.ingredients:
            await _replace_ingredients(session, meal, _raw_ingredients(ingredient_names))
        return
    await _apply_enrichment(session, meal, enr, keep_description=bool(meal.description))


async def create_meal(
    session: AsyncSession, llm: LLM, household: Household, created_by: uuid.UUID, body: MealCreate
) -> Meal:
    norm = normalize_name(body.name)
    if not norm:
        raise validation("Meal name must contain letters or numbers", field="name")
    clash = await session.scalar(select(Meal.id).where(Meal.household_id == household.id, Meal.normalized_name == norm))
    if clash:
        raise conflict("You already have a meal with that name")
    meal = Meal(
        household_id=household.id,
        name=body.name,
        normalized_name=norm,
        description=body.description,
        instructions=body.instructions,
        source="user",
        created_by=created_by,
        enrichment_status="pending",
        ingredients=[],
    )
    session.add(meal)
    await _run_enrichment(session, llm, household, meal, body.ingredients)
    await session.commit()
    return await get_meal(session, household.id, meal.id)


async def re_enrich(session: AsyncSession, llm: LLM, household: Household, meal: Meal) -> Meal:
    names = [i.name for i in meal.ingredients]
    await _run_enrichment(session, llm, household, meal, names)
    await session.commit()
    return await get_meal(session, household.id, meal.id)


async def update_meal(session: AsyncSession, household_id: uuid.UUID, meal: Meal, patch: MealPatch) -> Meal:
    if meal.source != "user":
        raise forbidden("Suggested meals cannot be edited")
    data = patch.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        norm = normalize_name(data["name"])
        clash = await session.scalar(
            select(Meal.id).where(Meal.household_id == household_id, Meal.normalized_name == norm, Meal.id != meal.id)
        )
        if clash:
            raise conflict("You already have a meal with that name")
        meal.name = " ".join(data["name"].split())
        meal.normalized_name = norm
    for field in ("description", "instructions", "prep_minutes", "meal_types"):
        if field in data and data[field] is not None:
            setattr(meal, field, data[field])
    if data.get("cuisine") is not None:
        meal.cuisine = slugify(data["cuisine"])
    if data.get("diet_tags") is not None:
        meal.diet_tags = [t for t in dict.fromkeys(data["diet_tags"]) if t in DIET_TAGS]
    if data.get("allergens") is not None:
        meal.allergens = [a for a in dict.fromkeys(data["allergens"]) if a in ALLERGENS]
    if patch.ingredients is not None:
        await _replace_ingredients(session, meal, patch.ingredients)
    await session.commit()
    return await get_meal(session, household_id, meal.id)


async def delete_meal(session: AsyncSession, meal: Meal) -> None:
    referenced = await session.scalar(
        select(func.count())
        .select_from(PlanEntry)
        .join(MealPlan, MealPlan.id == PlanEntry.plan_id)
        .where(PlanEntry.meal_id == meal.id, MealPlan.status == "active")
    )
    if referenced:
        raise conflict("This meal is in your current plan")
    await session.delete(meal)
    await session.commit()


async def feedback_summary(
    session: AsyncSession, household_id: uuid.UUID, meal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, FeedbackSummary]:
    if not meal_ids:
        return {}
    stmt = (
        select(
            MealFeedback.meal_id,
            MealFeedback.kind,
            func.count().label("n"),
            func.max(MealFeedback.created_at).label("last"),
        )
        .where(MealFeedback.household_id == household_id, MealFeedback.meal_id.in_(meal_ids))
        .group_by(MealFeedback.meal_id, MealFeedback.kind)
    )
    out: dict[uuid.UUID, FeedbackSummary] = {mid: FeedbackSummary() for mid in meal_ids}
    for meal_id, kind, n, last in (await session.execute(stmt)).all():
        s = out[meal_id]
        if kind == "up":
            s.up = n
        elif kind == "down":
            s.down = n
        elif kind == "cooked":
            s.cooked = n
            s.last_cooked_at = last
    return out


async def add_feedback(
    session: AsyncSession,
    household_id: uuid.UUID,
    member_id: uuid.UUID,
    meal: Meal,
    kind: str,
    plan_entry_id: uuid.UUID | None,
    comment: str | None,
) -> FeedbackSummary:
    if kind in ("up", "down"):
        await session.execute(
            delete(MealFeedback).where(
                MealFeedback.household_id == household_id,
                MealFeedback.member_id == member_id,
                MealFeedback.meal_id == meal.id,
                MealFeedback.kind.in_(["up", "down"]),
            )
        )
    if plan_entry_id is not None:
        entry = await session.get(PlanEntry, plan_entry_id)
        if entry is None or entry.meal_id != meal.id:
            plan_entry_id = None
    session.add(
        MealFeedback(
            household_id=household_id,
            member_id=member_id,
            meal_id=meal.id,
            plan_entry_id=plan_entry_id,
            kind=kind,
            comment=comment,
        )
    )
    await session.commit()
    return (await feedback_summary(session, household_id, [meal.id]))[meal.id]
