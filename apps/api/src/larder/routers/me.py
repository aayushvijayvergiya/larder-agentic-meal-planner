from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.deps import CurrentUser, get_current_user
from larder.db.session import get_session
from larder.schemas.common import HouseholdOut
from larder.schemas.me import MeOut, ProfileOut, ProfilePatch
from larder.services.profiles import update_profile

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> MeOut:
    return MeOut(
        profile=ProfileOut.model_validate(user.profile),
        household=HouseholdOut.from_model(user.household) if user.household else None,
        onboarding_status=user.profile.onboarding_status,
    )


@router.patch("/me", response_model=ProfileOut)
async def patch_me(
    patch: ProfilePatch,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await update_profile(session, user.profile, patch)
    return ProfileOut.model_validate(profile)
