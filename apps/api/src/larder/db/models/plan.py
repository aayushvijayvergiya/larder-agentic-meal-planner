import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from larder.db.base import Base, TimestampMixin
from larder.db.models.enums import job_mode_enum, job_origin_enum, job_status_enum, plan_scope_enum, plan_status_enum
from larder.db.models.meal import Meal


class MealPlan(Base, TimestampMixin):
    __tablename__ = "meal_plans"
    __table_args__ = (Index("ix_meal_plans_lookup", "household_id", "scope", "member_id", "status", "start_date"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(plan_scope_enum(), nullable=False)
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE")
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(plan_status_enum(), nullable=False, default="active", server_default="active")

    entries: Mapped[list["PlanEntry"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanEntry.date"
    )
    jobs: Mapped[list["PlanJob"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlanEntry(Base):
    __tablename__ = "plan_entries"
    __table_args__ = (UniqueConstraint("plan_id", "date", "slot_key", name="uq_plan_entries_plan_date_slot"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    slot_key: Mapped[str] = mapped_column(Text, nullable=False)
    meal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meals.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    covered_ingredients: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'")
    )
    missing_ingredients: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    plan: Mapped[MealPlan] = relationship(back_populates="entries")
    meal: Mapped[Meal] = relationship()
    variations: Mapped[list["PlanEntryVariation"]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class PlanEntryVariation(Base):
    __tablename__ = "plan_entry_variations"
    __table_args__ = (UniqueConstraint("plan_entry_id", "member_id", name="uq_plan_entry_variations_entry_member"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    plan_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_entries.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)

    entry: Mapped[PlanEntry] = relationship(back_populates="variations")


class PlanJob(Base):
    __tablename__ = "plan_jobs"
    __table_args__ = (Index("ix_plan_jobs_plan_status", "plan_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(job_mode_enum(), nullable=False)
    origin: Mapped[str] = mapped_column(job_origin_enum(), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    target_slot_key: Mapped[str | None] = mapped_column(Text)
    target_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    swap_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(job_status_enum(), nullable=False, default="queued", server_default="queued")
    inputs_hash: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[MealPlan] = relationship(back_populates="jobs")
