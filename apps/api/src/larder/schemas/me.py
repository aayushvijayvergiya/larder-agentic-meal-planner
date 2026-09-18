"""Profile schemas (LLD §6.3)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from larder.schemas.common import ActivityLevel, CookingSkill, DietType, HouseholdOut, OnboardingStatus, Sex
from larder.services.normalize import normalize_name, slugify


class MedicalCondition(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=280)


def _norm_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    out: list[str] = []
    for v in values:
        n = normalize_name(v)
        if n and n not in out:
            out.append(n)
    return out


def _slug_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    out: list[str] = []
    for v in values:
        s = slugify(v)
        if s and s not in out:
            out.append(s)
    return out


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    date_of_birth: date | None = None
    sex: Sex | None = None
    height_cm: int | None = Field(default=None, ge=50, le=250)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    activity_level: ActivityLevel | None = None
    diet_type: DietType | None = None
    cuisines: list[str] | None = Field(default=None, max_length=12)
    allergens: list[str] | None = Field(default=None, max_length=20)
    dislikes: list[str] | None = Field(default=None, max_length=20)
    likes: list[str] | None = Field(default=None, max_length=20)
    medical_conditions: list[MedicalCondition] | None = Field(default=None, max_length=10)
    medical_notes: str | None = Field(default=None, max_length=500)
    goals: list[str] | None = Field(default=None, max_length=7)
    cooking_skill: CookingSkill | None = None
    max_prep_minutes: int | None = Field(default=None, ge=5, le=240)

    @field_validator("allergens", "dislikes", "likes")
    @classmethod
    def _norm(cls, v):
        return _norm_list(v)

    @field_validator("cuisines", "goals")
    @classmethod
    def _slug(cls, v):
        return _slug_list(v)

    @field_validator("date_of_birth")
    @classmethod
    def _age_range(cls, v: date | None) -> date | None:
        if v is None:
            return v
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 5 or age > 120:
            raise ValueError("date of birth must give an age between 5 and 120")
        return v


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    date_of_birth: date | None
    sex: str | None
    height_cm: int | None
    weight_kg: float | None
    activity_level: str | None
    diet_type: str | None
    cuisines: list[str]
    allergens: list[str]
    dislikes: list[str]
    likes: list[str]
    medical_conditions: list[MedicalCondition]
    medical_notes: str | None
    goals: list[str]
    cooking_skill: str | None
    max_prep_minutes: int | None
    onboarding_status: OnboardingStatus
    created_at: datetime
    updated_at: datetime


class MeOut(BaseModel):
    profile: ProfileOut
    household: HouseholdOut | None
    onboarding_status: OnboardingStatus
