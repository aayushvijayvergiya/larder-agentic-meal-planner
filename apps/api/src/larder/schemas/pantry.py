"""Pantry schemas (LLD §6.6)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from larder.schemas.common import PantryCategory


class PantryItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    category: PantryCategory | None = None

    @field_validator("name")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be empty")
        return v


class PantryAddRequest(BaseModel):
    items: list[PantryItemIn] = Field(min_length=1, max_length=100)


class PantryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: PantryCategory
    is_available: bool
    updated_at: datetime


class PantryAddResponse(BaseModel):
    created: list[PantryItemOut]
    existing: list[PantryItemOut]


class PantryCategoryGroup(BaseModel):
    category: PantryCategory
    label: str
    items: list[PantryItemOut]


class PantryOut(BaseModel):
    categories: list[PantryCategoryGroup]
    total: int


class PantryItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    category: PantryCategory | None = None
    is_available: bool | None = None

    @field_validator("name")
    @classmethod
    def _trim(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be empty")
        return v


class SuggestionItem(BaseModel):
    name: str
    category: PantryCategory


class SuggestionsOut(BaseModel):
    items: list[SuggestionItem]
