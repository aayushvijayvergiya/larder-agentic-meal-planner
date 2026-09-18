"""Profile provisioning and updates (LLD §4.2, §6.3)."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.jwt import TokenClaims
from larder.db.models import Profile
from larder.schemas.me import ProfilePatch


async def get_or_create_profile(session: AsyncSession, claims: TokenClaims) -> Profile:
    """Just-in-time provisioning: the first authenticated call creates the profile row."""
    stmt = insert(Profile).values(id=claims.sub, email=claims.email).on_conflict_do_nothing(index_elements=["id"])
    await session.execute(stmt)
    await session.commit()
    profile = await session.get(Profile, claims.sub)
    assert profile is not None
    if claims.email and profile.email != claims.email:
        profile.email = claims.email
        await session.commit()
    return profile


def apply_patch(profile: Profile, patch: ProfilePatch) -> None:
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field == "medical_conditions" and value is not None:
            value = [dict(c) for c in value]  # JSONB list of {"name", "notes"}
        setattr(profile, field, value)


async def update_profile(session: AsyncSession, profile: Profile, patch: ProfilePatch) -> Profile:
    apply_patch(profile, patch)
    await session.commit()
    await session.refresh(profile)
    return profile
