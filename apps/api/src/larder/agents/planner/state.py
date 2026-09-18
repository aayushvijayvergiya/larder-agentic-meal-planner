"""Planner input, context and draft models (LLD §8.2)."""

from datetime import date
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from larder.agents.enrichment.schemas import IngredientDraft
from larder.schemas.common import SlotDef

__all__ = [
    "EntryDraft",
    "FixedEntryCtx",
    "IngredientCtx",
    "IngredientDraft",
    "MealCandidate",
    "MealCtx",
    "MemberCtx",
    "NewMealDraft",
    "PantryCtx",
    "PlanDraft",
    "PlannerInput",
    "PlannerState",
    "PlanningContext",
    "VariationDraft",
]


class PlannerInput(BaseModel):
    job_id: UUID
    plan_id: UUID
    household_id: UUID
    scope: Literal["family", "single"]
    member_id: UUID | None = None
    mode: Literal["week", "today", "slot"]
    start_date: date
    end_date: date
    target_date: date | None = None
    target_slot_key: str | None = None
    target_entry_id: UUID | None = None
    swap_reason: str | None = None


class MemberCtx(BaseModel):
    id: UUID
    display_name: str
    diet_type: str | None = None
    allergens: list[str] = []
    dislikes: list[str] = []
    likes: list[str] = []
    cuisines: list[str] = []
    medical_conditions: list[dict] = []
    medical_notes: str | None = None
    goals: list[str] = []
    cooking_skill: str | None = None
    max_prep_minutes: int | None = None
    age: int | None = None
    sex: str | None = None
    activity_level: str | None = None


class PantryCtx(BaseModel):
    name: str
    normalized_name: str
    category: str
    is_available: bool = True


class IngredientCtx(BaseModel):
    name: str
    normalized_name: str
    category: str
    is_staple: bool = False
    is_optional: bool = False


class MealCtx(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    cuisine: str | None = None
    meal_types: list[str] = []
    diet_tags: list[str] = []
    allergens: list[str] = []
    prep_minutes: int | None = None
    source: str = "user"
    ingredients: list[IngredientCtx] = []
    feedback_up: int = 0
    feedback_down: int = 0
    cooked_count: int = 0
    last_used_date: date | None = None


class FixedEntryCtx(BaseModel):
    date: date
    slot_key: str
    meal_name: str
    meal_id: UUID


class PlanningContext(BaseModel):
    members: list[MemberCtx]
    pantry: list[PantryCtx]
    library: list[MealCtx]
    slots: list[SlotDef]
    recent_meal_ids: list[UUID] = []
    fixed_entries: list[FixedEntryCtx] = []
    requested: list[tuple[date, str]] = []
    library_count_and_max_updated: str = "0:"

    @property
    def pantry_norms(self) -> set[str]:
        return {p.normalized_name for p in self.pantry if p.is_available}


class MealCandidate(BaseModel):
    meal: MealCtx
    coverage: float
    score: float
    covered: list[str]
    missing: list[IngredientCtx]


class NewMealDraft(BaseModel):
    name: str = Field(max_length=80)
    description: str = Field(default="", max_length=240)
    cuisine: str = Field(default="home", max_length=40)
    meal_types: list[str] = []
    diet_tags: list[str] = []
    allergens: list[str] = []
    prep_minutes: int = Field(default=30, ge=5, le=240)
    ingredients: list[IngredientDraft] = Field(min_length=2, max_length=20)


class VariationDraft(BaseModel):
    member_id: UUID
    note: str = Field(max_length=120)


class EntryDraft(BaseModel):
    date: date
    slot_key: str
    existing_meal_id: UUID | None = None
    new_meal: NewMealDraft | None = None
    reason: str = Field(default="", max_length=160)
    variations: list[VariationDraft] = []

    @model_validator(mode="after")
    def _exactly_one_meal(self) -> "EntryDraft":
        if (self.existing_meal_id is None) == (self.new_meal is None):
            raise ValueError("entry must have exactly one of existing_meal_id or new_meal")
        return self


class PlanDraft(BaseModel):
    entries: list[EntryDraft]


class PlannerState(TypedDict, total=False):
    input: PlannerInput
    context: PlanningContext | None
    inputs_hash: str | None
    shortlist: list[MealCandidate]
    draft: PlanDraft | None
    violations: list[str]
    warnings: list[str]
    bad_entry_indexes: list[int]
    attempts: int
    used_fallback: bool
    persisted: bool
    entries_written: int
    llm_error: str | None
