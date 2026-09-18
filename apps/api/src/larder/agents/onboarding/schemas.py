"""Onboarding data schemas (LLD §8.1)."""

from datetime import date

from pydantic import BaseModel, Field

from larder.schemas.me import MedicalCondition


class ProfileDraft(BaseModel):
    display_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    activity_level: str | None = None
    diet_type: str | None = None
    cuisines: list[str] | None = None
    allergens: list[str] | None = None
    dislikes: list[str] | None = None
    likes: list[str] | None = None
    medical_conditions: list[MedicalCondition] | None = None
    medical_notes: str | None = None
    goals: list[str] | None = None
    cooking_skill: str | None = None
    max_prep_minutes: int | None = None


class ParsedFieldAnswer(BaseModel):
    """What the LLM extracts from a free-text answer. value is None when the text does not answer the question."""

    value: str | float | list[str] | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class Progress(BaseModel):
    answered: int
    total: int
