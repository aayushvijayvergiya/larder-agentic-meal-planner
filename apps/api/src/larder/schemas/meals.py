"""Meal library schemas (LLD §6.7)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from larder.agents.enrichment.schemas import IngredientDraft
from larder.schemas.common import FeedbackKind, PantryCategory


class MealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    ingredients: list[str] | None = Field(default=None, max_length=25)
    instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("ingredients")
    @classmethod
    def _clean(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [" ".join(x.split()) for x in v if x and x.strip()]


class MealPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    cuisine: str | None = Field(default=None, max_length=40)
    meal_types: list[str] | None = None
    diet_tags: list[str] | None = None
    allergens: list[str] | None = None
    prep_minutes: int | None = Field(default=None, ge=5, le=240)
    instructions: str | None = Field(default=None, max_length=4000)
    ingredients: list[IngredientDraft] | None = Field(default=None, min_length=1, max_length=25)


class IngredientOut(BaseModel):
    name: str
    category: PantryCategory
    is_staple: bool
    is_optional: bool


class FeedbackSummary(BaseModel):
    up: int = 0
    down: int = 0
    cooked: int = 0
    last_cooked_at: datetime | None = None


class MealOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    cuisine: str | None
    meal_types: list[str]
    diet_tags: list[str]
    allergens: list[str]
    prep_minutes: int | None
    instructions: str | None
    source: str
    enrichment_status: str
    ingredients: list[IngredientOut]
    feedback: FeedbackSummary

    @classmethod
    def from_model(cls, meal, feedback: FeedbackSummary | None = None) -> "MealOut":
        return cls(
            id=meal.id,
            name=meal.name,
            description=meal.description,
            cuisine=meal.cuisine,
            meal_types=list(meal.meal_types),
            diet_tags=list(meal.diet_tags),
            allergens=list(meal.allergens),
            prep_minutes=meal.prep_minutes,
            instructions=meal.instructions,
            source=meal.source,
            enrichment_status=meal.enrichment_status,
            ingredients=[
                IngredientOut(name=i.name, category=i.category, is_staple=i.is_staple, is_optional=i.is_optional)
                for i in meal.ingredients
            ],
            feedback=feedback or FeedbackSummary(),
        )


class MealsOut(BaseModel):
    meals: list[MealOut]


class FeedbackCreate(BaseModel):
    kind: FeedbackKind
    plan_entry_id: UUID | None = None
    comment: str | None = Field(default=None, max_length=280)


class FeedbackOut(BaseModel):
    feedback: FeedbackSummary
