from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TickReport(BaseModel):
    ran_at: datetime
    households_checked: int = 0
    weekly_enqueued: list[UUID] = Field(default_factory=list)
    daily_enqueued: list[UUID] = Field(default_factory=list)
    skipped: int = 0
    cleaned_plans: int = 0
