"""Households, invites and membership (LLD §6.5, §7.5)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from larder.auth.deps import CurrentUser
from larder.db.models import DEFAULT_SLOTS, Household, HouseholdInvite, HouseholdMember, Profile
from larder.errors import conflict, forbidden, not_found, validation
from larder.schemas.households import HouseholdPatch

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def active_scopes(household) -> list[tuple[str, uuid.UUID | None]]:
    """Scopes the scheduler keeps plans for (LLD §7.5)."""
    members = list(household.members)
    scopes: list[tuple[str, uuid.UUID | None]] = []
    if len(members) > 1 and any(m.preferred_view == "family" for m in members):
        scopes.append(("family", None))
    scopes.extend(("single", m.user_id) for m in members if m.preferred_view == "single")
    return scopes


async def get_household(session: AsyncSession, household_id: uuid.UUID) -> Household | None:
    stmt = (
        select(Household)
        .where(Household.id == household_id)
        .options(selectinload(Household.members).selectinload(HouseholdMember.profile))
    )
    return await session.scalar(stmt)


def own_household(user: CurrentUser, household_id: uuid.UUID) -> Household:
    """The caller's household, or not_found when the path id is not theirs (never leak existence)."""
    if user.household is None or user.household.id != household_id:
        raise not_found("Household not found")
    return user.household


async def create_implicit_household(session: AsyncSession, profile: Profile) -> Household:
    name = f"{profile.display_name}'s kitchen" if profile.display_name else "My kitchen"
    household = Household(name=name, owner_id=profile.id, is_implicit=True, slots=list(DEFAULT_SLOTS))
    session.add(household)
    await session.flush()
    session.add(HouseholdMember(household_id=household.id, user_id=profile.id, role="owner", preferred_view="single"))
    await session.flush()
    return household


async def update_household(session: AsyncSession, household: Household, patch: HouseholdPatch) -> Household:
    data = patch.model_dump(exclude_unset=True)
    if "slots" in data and data["slots"] is not None:
        data["slots"] = [s.model_dump() for s in patch.slots]  # type: ignore[union-attr]
    if data.get("name"):
        household.is_implicit = False
    for field, value in data.items():
        if value is not None:
            setattr(household, field, value)
    await session.commit()
    return await get_household(session, household.id)  # type: ignore[return-value]


def _new_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))


async def generate_invite(
    session: AsyncSession,
    household: Household,
    created_by: uuid.UUID,
    expires_in_days: int = 7,
    max_uses: int = 10,
) -> HouseholdInvite:
    code = _new_code()
    while await session.scalar(select(HouseholdInvite.id).where(HouseholdInvite.code == code)):
        code = _new_code()
    invite = HouseholdInvite(
        household_id=household.id,
        code=code,
        created_by=created_by,
        expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        max_uses=max_uses,
    )
    session.add(invite)
    await session.flush()
    return invite


def _invite_usable(invite: HouseholdInvite, now: datetime) -> bool:
    return invite.revoked_at is None and invite.expires_at > now and invite.uses < invite.max_uses


async def list_invites(session: AsyncSession, household: Household) -> list[HouseholdInvite]:
    now = datetime.now(UTC)
    rows = (
        await session.scalars(
            select(HouseholdInvite)
            .where(HouseholdInvite.household_id == household.id)
            .order_by(HouseholdInvite.created_at.desc())
        )
    ).all()
    return [i for i in rows if _invite_usable(i, now)]


async def revoke_invite(session: AsyncSession, household: Household, code: str) -> None:
    invite = await session.scalar(
        select(HouseholdInvite).where(HouseholdInvite.household_id == household.id, HouseholdInvite.code == code)
    )
    if invite is None:
        raise not_found("Invite not found")
    invite.revoked_at = datetime.now(UTC)
    await session.commit()


async def _delete_household(session: AsyncSession, household_id: uuid.UUID) -> None:
    await session.execute(delete(Household).where(Household.id == household_id))


async def join_by_code(session: AsyncSession, user: CurrentUser, code: str) -> Household:
    invite = await session.scalar(select(HouseholdInvite).where(HouseholdInvite.code == code))
    if invite is None:
        raise not_found("Invite code not found")
    if not _invite_usable(invite, datetime.now(UTC)):
        raise conflict("This invite code has expired or been used up")
    current = user.household
    assert current is not None and user.membership is not None
    if invite.household_id == current.id:
        raise conflict("You are already a member of this household")
    member_count = await session.scalar(
        select(func.count()).select_from(HouseholdMember).where(HouseholdMember.household_id == current.id)
    )
    if not current.is_implicit or member_count != 1:
        raise conflict("Leave your current household first")

    await session.delete(user.membership)
    await session.flush()
    await _delete_household(session, current.id)
    session.add(
        HouseholdMember(
            household_id=invite.household_id, user_id=user.profile.id, role="member", preferred_view="family"
        )
    )
    invite.uses += 1
    await session.commit()
    return await get_household(session, invite.household_id)  # type: ignore[return-value]


async def remove_member(
    session: AsyncSession, actor: CurrentUser, household_id: uuid.UUID, user_id: uuid.UUID
) -> Household | None:
    """Owner removes a member, or a member removes themselves. Returns the removed user's new implicit household."""
    household = own_household(actor, household_id)
    assert actor.membership is not None
    members = {m.user_id: m for m in household.members}
    target = members.get(user_id)
    if target is None:
        raise not_found("Member not found")
    if user_id == actor.profile.id:
        if actor.membership.role == "owner":
            if len(members) > 1:
                raise conflict("Remove the other members before leaving; the owner cannot leave first")
            raise conflict("You are the only member of this household")
    elif actor.membership.role != "owner":
        raise forbidden("Only the household owner can remove members")

    profile = target.profile
    await session.delete(target)
    await session.flush()
    new_household = await create_implicit_household(session, profile)
    await session.commit()
    return await get_household(session, new_household.id)


async def set_preferred_view(session: AsyncSession, user: CurrentUser, view: str) -> HouseholdMember:
    assert user.household is not None and user.membership is not None
    if view == "family" and len(user.household.members) < 2:
        raise validation("Family view needs at least two members", field="preferred_view")
    user.membership.preferred_view = view
    await session.commit()
    await session.refresh(user.membership)
    return user.membership
