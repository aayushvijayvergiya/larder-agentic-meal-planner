import uuid

from sqlalchemy import Boolean, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from larder.db.base import Base, TimestampMixin
from larder.db.models.enums import enrichment_enum, meal_source_enum, pantry_category_enum


class Meal(Base, TimestampMixin):
    __tablename__ = "meals"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_meals_household_name"),
        Index("ix_meals_household_source", "household_id", "source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cuisine: Mapped[str | None] = mapped_column(Text)
    meal_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'")
    )
    diet_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("'{}'"))
    prep_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    instructions: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(meal_source_enum(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    enrichment_status: Mapped[str] = mapped_column(
        enrichment_enum(), nullable=False, default="pending", server_default="pending"
    )

    ingredients: Mapped[list["MealIngredient"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", order_by="MealIngredient.position"
    )


class MealIngredient(Base):
    __tablename__ = "meal_ingredients"
    __table_args__ = (UniqueConstraint("meal_id", "normalized_name", name="uq_meal_ingredients_meal_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    meal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meals.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(pantry_category_enum(), nullable=False)
    is_staple: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    meal: Mapped[Meal] = relationship(back_populates="ingredients")
