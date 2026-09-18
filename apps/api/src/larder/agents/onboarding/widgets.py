"""Widget specs rendered by the clients (LLD §8.1)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from larder.agents.onboarding.schemas import ProfileDraft


class TextWidget(BaseModel):
    type: Literal["text"] = "text"
    placeholder: str = ""
    multiline: bool = False
    max_length: int = 200


class NumberWidget(BaseModel):
    type: Literal["number"] = "number"
    unit: str
    min: float
    max: float
    step: float = 1


class DateWidget(BaseModel):
    type: Literal["date"] = "date"
    min: date
    max: date


class Option(BaseModel):
    value: str
    label: str
    description: str | None = None


class SingleSelectWidget(BaseModel):
    type: Literal["single_select"] = "single_select"
    options: list[Option]


class MultiSelectWidget(BaseModel):
    type: Literal["multi_select"] = "multi_select"
    options: list[Option]
    allow_custom: bool = False
    min: int = 0
    max: int = 20


class ChipsWidget(BaseModel):
    type: Literal["chips"] = "chips"
    suggestions: list[str] = []
    placeholder: str = ""
    max: int = 20


class ReviewWidget(BaseModel):
    type: Literal["review"] = "review"
    draft: ProfileDraft


Widget = Annotated[
    TextWidget | NumberWidget | DateWidget | SingleSelectWidget | MultiSelectWidget | ChipsWidget | ReviewWidget,
    Field(discriminator="type"),
]

widget_adapter: TypeAdapter = TypeAdapter(Widget)


def parse_widget(data: dict | None):
    return widget_adapter.validate_python(data) if data is not None else None
