"""Shared API schemas (LLD §6.1)."""

from datetime import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Sex = Literal["female", "male", "other", "prefer_not_to_say"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
DietType = Literal["omnivore", "vegetarian", "eggetarian", "vegan", "pescatarian", "jain", "other"]
CookingSkill = Literal["beginner", "intermediate", "advanced"]
OnboardingStatus = Literal["pending", "in_progress", "complete"]
MemberRole = Literal["owner", "member"]
View = Literal["single", "family"]
PantryCategory = Literal[
    "spices",
    "grains",
    "pulses",
    "flours",
    "dairy",
    "vegetables",
    "fruits",
    "proteins",
    "condiments",
    "oils",
    "snacks",
    "beverages",
    "frozen",
    "other",
]
PlanScope = Literal["family", "single"]
JobMode = Literal["week", "today", "slot"]
JobStatus = Literal["queued", "running", "ready", "failed"]
FeedbackKind = Literal["up", "down", "cooked", "skipped"]


class SlotDef(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,30}$")
    label: str = Field(min_length=1, max_length=40)
    order: int = Field(ge=1, le=10)


class MemberSummary(BaseModel):
    user_id: UUID
    display_name: str | None
    role: MemberRole
    preferred_view: View


class HouseholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    timezone: str
    slots: list[SlotDef]
    weekly_refresh_day: int
    weekly_refresh_time: time
    daily_refresh_time: time
    is_implicit: bool
    members: list[MemberSummary]

    @classmethod
    def from_model(cls, household) -> "HouseholdOut":
        return cls(
            id=household.id,
            name=household.name,
            owner_id=household.owner_id,
            timezone=household.timezone,
            slots=[SlotDef(**s) for s in sorted(household.slots, key=lambda s: s["order"])],
            weekly_refresh_day=household.weekly_refresh_day,
            weekly_refresh_time=household.weekly_refresh_time,
            daily_refresh_time=household.daily_refresh_time,
            is_implicit=household.is_implicit,
            members=[
                MemberSummary(
                    user_id=m.user_id,
                    display_name=m.profile.display_name if m.profile else None,
                    role=m.role,
                    preferred_view=m.preferred_view,
                )
                for m in household.members
            ],
        )
