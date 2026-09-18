from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.deps import CurrentUser, require_household, require_owner
from larder.db.session import get_session
from larder.schemas.common import HouseholdOut, MemberSummary
from larder.schemas.households import HouseholdPatch, InviteCreate, InviteOut, JoinRequest, PreferredViewPatch
from larder.services import households as svc

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/me", response_model=HouseholdOut)
async def my_household(user: CurrentUser = Depends(require_household)) -> HouseholdOut:
    return HouseholdOut.from_model(user.household)


@router.post("/join", response_model=HouseholdOut)
async def join(
    body: JoinRequest,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> HouseholdOut:
    household = await svc.join_by_code(session, user, body.code)
    return HouseholdOut.from_model(household)


@router.patch("/{household_id}", response_model=HouseholdOut)
async def patch_household(
    household_id: UUID,
    patch: HouseholdPatch,
    user: CurrentUser = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> HouseholdOut:
    household = svc.own_household(user, household_id)
    return HouseholdOut.from_model(await svc.update_household(session, household, patch))


@router.post("/{household_id}/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    household_id: UUID,
    body: InviteCreate | None = None,
    user: CurrentUser = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> InviteOut:
    body = body or InviteCreate()
    household = svc.own_household(user, household_id)
    invite = await svc.generate_invite(session, household, user.profile.id, body.expires_in_days, body.max_uses)
    await session.commit()
    return InviteOut(code=invite.code, expires_at=invite.expires_at, max_uses=invite.max_uses, uses=invite.uses)


@router.get("/{household_id}/invites", response_model=list[InviteOut])
async def list_invites(
    household_id: UUID,
    user: CurrentUser = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> list[InviteOut]:
    household = svc.own_household(user, household_id)
    return [
        InviteOut(code=i.code, expires_at=i.expires_at, max_uses=i.max_uses, uses=i.uses)
        for i in await svc.list_invites(session, household)
    ]


@router.delete("/{household_id}/invites/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    household_id: UUID,
    code: str,
    user: CurrentUser = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> Response:
    household = svc.own_household(user, household_id)
    await svc.revoke_invite(session, household, code.upper())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{household_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    household_id: UUID,
    user_id: UUID,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await svc.remove_member(session, user, household_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{household_id}/members/me", response_model=MemberSummary)
async def set_preferred_view(
    household_id: UUID,
    body: PreferredViewPatch,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> MemberSummary:
    svc.own_household(user, household_id)
    m = await svc.set_preferred_view(session, user, body.preferred_view)
    return MemberSummary(
        user_id=m.user_id, display_name=user.profile.display_name, role=m.role, preferred_view=m.preferred_view
    )
