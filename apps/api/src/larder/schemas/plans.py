"""Plan schemas (LLD §6.8)."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from larder.schemas.common import JobMode, JobStatus, PantryCategory, PlanScope
from larder.schemas.meals import MealOut


class MissingIngredientOut(BaseModel):
    name: str
    category: PantryCategory
    is_optional: bool = False


class VariationOut(BaseModel):
    member_id: UUID
    display_name: str | None
    note: str


class PlanEntryOut(BaseModel):
    id: UUID
    date: dt.date
    slot_key: str
    slot_label: str
    meal: MealOut
    reason: str
    covered_ingredients: list[str]
    missing_ingredients: list[MissingIngredientOut]
    variations: list[VariationOut]
    my_feedback: Literal["up", "down"] | None
    cooked_count: int


class PlanDayOut(BaseModel):
    date: dt.date
    entries: list[PlanEntryOut]


class CoverageOut(BaseModel):
    on_hand: int
    needed: int


class UnusedItemOut(BaseModel):
    name: str
    category: PantryCategory


class PlanOut(BaseModel):
    id: UUID
    scope: PlanScope
    member_id: UUID | None
    start_date: dt.date
    end_date: dt.date
    days: list[PlanDayOut]
    coverage: CoverageOut
    unused_pantry: list[UnusedItemOut]


class ActiveJobOut(BaseModel):
    id: UUID
    mode: JobMode
    status: JobStatus
    created_at: dt.datetime


class CurrentPlanOut(BaseModel):
    plan: PlanOut | None
    active_job: ActiveJobOut | None


class GenerateRequest(BaseModel):
    scope: PlanScope
    mode: Literal["week", "today"]
    date: dt.date | None = None


class GenerateResponse(BaseModel):
    job_id: UUID
    plan_id: UUID


class SwapRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=160)


class SwapResponse(BaseModel):
    job_id: UUID


class ShoppingItemOut(BaseModel):
    name: str
    meals: list[str]


class ShoppingGroupOut(BaseModel):
    category: PantryCategory
    label: str
    items: list[ShoppingItemOut]


class ShoppingListOut(BaseModel):
    from_date: dt.date
    to_date: dt.date
    groups: list[ShoppingGroupOut]
    total: int


class JobOut(BaseModel):
    id: UUID
    plan_id: UUID
    mode: JobMode
    status: JobStatus
    error: str | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
