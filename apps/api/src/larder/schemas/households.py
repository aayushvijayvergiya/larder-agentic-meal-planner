"""Household schemas (LLD §6.5)."""

from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from larder.schemas.common import SlotDef, View


class HouseholdPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    timezone: str | None = None
    slots: list[SlotDef] | None = Field(default=None, min_length=1, max_length=6)
    weekly_refresh_day: int | None = Field(default=None, ge=0, le=6)
    weekly_refresh_time: time | None = None
    daily_refresh_time: time | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown timezone") from exc
        return v

    @field_validator("slots")
    @classmethod
    def _unique_keys(cls, v: list[SlotDef] | None) -> list[SlotDef] | None:
        if v is None:
            return v
        keys = [s.key for s in v]
        if len(set(keys)) != len(keys):
            raise ValueError("slot keys must be unique")
        return sorted(v, key=lambda s: s.order)


class InviteCreate(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=90)
    max_uses: int = Field(default=10, ge=1, le=100)


class InviteOut(BaseModel):
    code: str
    expires_at: datetime
    max_uses: int
    uses: int


class JoinRequest(BaseModel):
    code: str = Field(min_length=8, max_length=8)

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class PreferredViewPatch(BaseModel):
    preferred_view: View
