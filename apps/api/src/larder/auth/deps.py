"""Request-scoped auth dependencies (LLD §4.2, §4.3)."""

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.auth.jwt import verify_token
from larder.db.models import Household, HouseholdMember, Profile
from larder.db.session import get_session
from larder.errors import forbidden, onboarding_incomplete, unauthorized
from larder.logging import user_id_var
from larder.services.profiles import get_or_create_profile


@dataclass
class CurrentUser:
    profile: Profile
    household: Household | None
    membership: HouseholdMember | None

    @property
    def household_id(self):
        return self.household.id if self.household else None


async def load_membership(session: AsyncSession, user_id) -> HouseholdMember | None:
    stmt = (
        select(HouseholdMember)
        .where(HouseholdMember.user_id == user_id)
        .options(
            selectinload(HouseholdMember.household)
            .selectinload(Household.members)
            .selectinload(HouseholdMember.profile)
        )
    )
    return await session.scalar(stmt)


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> CurrentUser:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise unauthorized()
    claims = verify_token(auth[7:].strip(), request.app.state.settings)
    profile = await get_or_create_profile(session, claims)
    membership = await load_membership(session, profile.id)
    request.state.user_id = str(profile.id)
    user_id_var.set(str(profile.id))
    return CurrentUser(profile=profile, household=membership.household if membership else None, membership=membership)


async def require_household(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.household is None or user.profile.onboarding_status != "complete":
        raise onboarding_incomplete()
    return user


async def require_owner(user: CurrentUser = Depends(require_household)) -> CurrentUser:
    if user.membership is None or user.membership.role != "owner":
        raise forbidden("Only the household owner can do this")
    return user
