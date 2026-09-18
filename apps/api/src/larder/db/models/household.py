import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, Text, Time, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from larder.db.base import Base, TimestampMixin
from larder.db.models.enums import member_role_enum, view_enum
from larder.db.models.profile import Profile

DEFAULT_SLOTS: list[dict] = [
    {"key": "breakfast", "label": "Breakfast", "order": 1},
    {"key": "lunch", "label": "Lunch", "order": 2},
    {"key": "snack", "label": "Snack", "order": 3},
    {"key": "dinner", "label": "Dinner", "order": 4},
]


class Household(Base, TimestampMixin):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata")
    slots: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=lambda: list(DEFAULT_SLOTS))
    weekly_refresh_day: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=6, server_default="6")
    weekly_refresh_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(18, 0), server_default="18:00")
    daily_refresh_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(6, 0), server_default="06:00")
    is_implicit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    members: Mapped[list["HouseholdMember"]] = relationship(
        back_populates="household", cascade="all, delete-orphan", order_by="HouseholdMember.joined_at"
    )


class HouseholdMember(Base):
    __tablename__ = "household_members"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True, unique=True
    )
    role: Mapped[str] = mapped_column(member_role_enum(), nullable=False)
    preferred_view: Mapped[str] = mapped_column(view_enum(), nullable=False, default="family", server_default="family")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    household: Mapped[Household] = relationship(back_populates="members")
    profile: Mapped[Profile] = relationship(back_populates="membership", foreign_keys=[user_id])


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=10, server_default="10")
    uses: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
