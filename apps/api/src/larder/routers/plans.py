from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.deps import CurrentUser, require_household
from larder.db.session import get_session
from larder.schemas.common import PlanScope
from larder.schemas.plans import (
    CurrentPlanOut,
    GenerateRequest,
    GenerateResponse,
    JobOut,
    ShoppingListOut,
    SwapRequest,
    SwapResponse,
)
from larder.services import plans as svc

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/current", response_model=CurrentPlanOut)
async def current_plan(
    scope: PlanScope | None = Query(default=None),
    on_date: date | None = Query(default=None, alias="date"),
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> CurrentPlanOut:
    scope = scope or user.membership.preferred_view
    svc.validate_scope(user.household, scope)
    return await svc.get_current_plan(session, user.household, user.profile.id, scope, on_date)


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate(
    body: GenerateRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    svc.validate_scope(user.household, body.scope)
    job_id, plan_id = await svc.request_generation(
        session,
        household=user.household,
        scope=body.scope,
        member_id=user.profile.id if body.scope == "single" else None,
        mode=body.mode,
        on_date=body.date,
        origin="user",
        background=background,
        llm=request.app.state.llm,
    )
    return GenerateResponse(job_id=job_id, plan_id=plan_id)


@router.post("/{plan_id}/entries/{entry_id}/swap", response_model=SwapResponse, status_code=status.HTTP_202_ACCEPTED)
async def swap(
    plan_id: UUID,
    entry_id: UUID,
    body: SwapRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> SwapResponse:
    job_id = await svc.request_swap(
        session,
        household=user.household,
        plan_id=plan_id,
        entry_id=entry_id,
        reason=body.reason,
        background=background,
        llm=request.app.state.llm,
    )
    return SwapResponse(job_id=job_id)


@router.get("/{plan_id}/shopping-list", response_model=ShoppingListOut)
async def shopping_list(
    plan_id: UUID, user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> ShoppingListOut:
    return await svc.get_shopping_list(session, user.household, plan_id)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job(
    job_id: UUID, user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> JobOut:
    j = await svc.get_job(session, user.household, job_id)
    return JobOut(
        id=j.id,
        plan_id=j.plan_id,
        mode=j.mode,
        status=j.status,
        error=j.error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
    )
