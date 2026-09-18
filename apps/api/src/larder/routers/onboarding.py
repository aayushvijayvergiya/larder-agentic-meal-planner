from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from larder.agents.onboarding.graph import TurnResult, current_state, run_turn, thread_id_for
from larder.agents.onboarding.schemas import ProfileDraft
from larder.auth.deps import CurrentUser, get_current_user
from larder.db.session import get_session
from larder.errors import conflict, not_found
from larder.schemas.common import HouseholdOut
from larder.schemas.me import ProfileOut, ProfilePatch
from larder.schemas.onboarding import CompleteRequest, CompleteResponse, TurnRequest, TurnResponse
from larder.services.households import create_implicit_household, get_household
from larder.services.profiles import apply_patch

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _response(user_id: str, t: TurnResult) -> TurnResponse:
    return TurnResponse(
        thread_id=thread_id_for(user_id),
        message=t.message,
        widget=t.widget,
        field=t.field,
        draft=t.draft,
        progress=t.progress,
        is_complete=t.is_complete,
    )


def _check_thread(user: CurrentUser, thread_id: str) -> str:
    uid = str(user.profile.id)
    if thread_id != thread_id_for(uid):
        raise not_found("Onboarding session not found")
    return uid


@router.post("/start", response_model=TurnResponse)
async def start(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TurnResponse:
    if user.profile.onboarding_status == "complete":
        raise conflict("Onboarding is already complete")
    uid = str(user.profile.id)
    if user.profile.onboarding_status != "in_progress":
        user.profile.onboarding_status = "in_progress"
        user.profile.onboarding_thread_id = thread_id_for(uid)
        await session.commit()
    t = await run_turn(request.app.state.onboarding_graph, request.app.state.llm, uid, None)
    return _response(uid, t)


@router.post("/turn", response_model=TurnResponse)
async def turn(
    body: TurnRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> TurnResponse:
    uid = _check_thread(user, body.thread_id)
    if user.profile.onboarding_status == "complete":
        raise conflict("Onboarding is already complete")
    t = await run_turn(
        request.app.state.onboarding_graph, request.app.state.llm, uid, body.answer.model_dump(mode="json")
    )
    return _response(uid, t)


@router.post("/complete", response_model=CompleteResponse)
async def complete(
    body: CompleteRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompleteResponse:
    uid = _check_thread(user, body.thread_id)
    if user.profile.onboarding_status == "complete" and user.household is not None:
        return CompleteResponse(
            profile=ProfileOut.model_validate(user.profile),
            household=HouseholdOut.from_model(user.household),
            first_plan_job_id=None,
        )
    state = await current_state(request.app.state.onboarding_graph, uid)
    if not state or not state.get("is_complete"):
        raise conflict("Please answer all the questions before confirming")
    draft = ProfileDraft(**(state.get("draft") or {}))
    apply_patch(user.profile, ProfilePatch(**draft.model_dump(exclude_none=True)))
    if body.overrides is not None:
        apply_patch(user.profile, body.overrides)
    user.profile.onboarding_status = "complete"
    household = await create_implicit_household(session, user.profile)
    await session.commit()
    household = await get_household(session, household.id)
    await session.refresh(user.profile)
    first_job_id = await request.app.state.first_plan_hook(
        session, user.profile, household, background, request.app.state.llm
    )
    return CompleteResponse(
        profile=ProfileOut.model_validate(user.profile),
        household=HouseholdOut.from_model(household),
        first_plan_job_id=first_job_id,
    )
