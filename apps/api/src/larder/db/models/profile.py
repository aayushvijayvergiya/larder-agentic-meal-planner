import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from larder.db.base import Base, TimestampMixin
from larder.db.models.enums import activity_enum, diet_enum, onboarding_enum, sex_enum, skill_enum

if TYPE_CHECKING:
    from larder.db.models.household import HouseholdMember


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(sex_enum())
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    activity_level: Mapped[str | None] = mapped_column(activity_enum())
    diet_type: Mapped[str | None] = mapped_column(diet_enum())
    cuisines: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    dislikes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    likes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    medical_conditions: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    medical_notes: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    cooking_skill: Mapped[str | None] = mapped_column(skill_enum())
    max_prep_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    onboarding_status: Mapped[str] = mapped_column(
        onboarding_enum(), nullable=False, default="pending", server_default="pending"
    )
    onboarding_thread_id: Mapped[str | None] = mapped_column(Text)

    membership: Mapped["HouseholdMember | None"] = relationship(
        back_populates="profile", uselist=False, foreign_keys="HouseholdMember.user_id"
    )
