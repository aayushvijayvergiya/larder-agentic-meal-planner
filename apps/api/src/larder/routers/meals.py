from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.deps import CurrentUser, require_household
from larder.db.session import get_session
from larder.schemas.meals import FeedbackCreate, FeedbackOut, MealCreate, MealOut, MealPatch, MealsOut
from larder.services import meals as svc

router = APIRouter(prefix="/meals", tags=["meals"])


async def _out(session: AsyncSession, household_id: UUID, meal) -> MealOut:
    summary = await svc.feedback_summary(session, household_id, [meal.id])
    return MealOut.from_model(meal, summary.get(meal.id))


@router.get("", response_model=MealsOut)
async def list_meals(
    query: str | None = Query(default=None, max_length=80),
    meal_type: str | None = Query(default=None, max_length=32),
    source: Literal["user", "generated", "all"] = "user",
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> MealsOut:
    meals = await svc.list_meals(session, user.household_id, query, meal_type, source)
    summaries = await svc.feedback_summary(session, user.household_id, [m.id for m in meals])
    return MealsOut(meals=[MealOut.from_model(m, summaries.get(m.id)) for m in meals])


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(
    body: MealCreate,
    request: Request,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> MealOut:
    meal = await svc.create_meal(session, request.app.state.llm, user.household, user.profile.id, body)
    return await _out(session, user.household_id, meal)


@router.get("/{meal_id}", response_model=MealOut)
async def get_meal(
    meal_id: UUID, user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> MealOut:
    return await _out(session, user.household_id, await svc.get_meal(session, user.household_id, meal_id))


@router.patch("/{meal_id}", response_model=MealOut)
async def patch_meal(
    meal_id: UUID,
    patch: MealPatch,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> MealOut:
    meal = await svc.get_meal(session, user.household_id, meal_id)
    return await _out(session, user.household_id, await svc.update_meal(session, user.household_id, meal, patch))


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: UUID, user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> Response:
    meal = await svc.get_meal(session, user.household_id, meal_id)
    await svc.delete_meal(session, meal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{meal_id}/enrich", response_model=MealOut)
async def enrich(
    meal_id: UUID,
    request: Request,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> MealOut:
    meal = await svc.get_meal(session, user.household_id, meal_id)
    meal = await svc.re_enrich(session, request.app.state.llm, user.household, meal)
    return await _out(session, user.household_id, meal)


@router.post("/{meal_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def feedback(
    meal_id: UUID,
    body: FeedbackCreate,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> FeedbackOut:
    meal = await svc.get_meal(session, user.household_id, meal_id)
    summary = await svc.add_feedback(
        session, user.household_id, user.profile.id, meal, body.kind, body.plan_entry_id, body.comment
    )
    return FeedbackOut(feedback=summary)
