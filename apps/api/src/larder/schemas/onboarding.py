"""Onboarding API schemas (LLD §6.4)."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from larder.agents.onboarding.schemas import ProfileDraft, Progress
from larder.agents.onboarding.widgets import Widget
from larder.schemas.common import HouseholdOut
from larder.schemas.me import ProfileOut, ProfilePatch


class WidgetAnswer(BaseModel):
    kind: Literal["widget"] = "widget"
    value: Any


class TextAnswer(BaseModel):
    kind: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=500)


Answer = Annotated[WidgetAnswer | TextAnswer, Field(discriminator="kind")]


class TurnRequest(BaseModel):
    thread_id: str
    answer: Answer


class TurnResponse(BaseModel):
    thread_id: str
    message: str
    widget: Widget | None
    field: str | None
    draft: ProfileDraft
    progress: Progress
    is_complete: bool


class CompleteRequest(BaseModel):
    thread_id: str
    overrides: ProfilePatch | None = None


class CompleteResponse(BaseModel):
    profile: ProfileOut
    household: HouseholdOut
    first_plan_job_id: UUID | None
