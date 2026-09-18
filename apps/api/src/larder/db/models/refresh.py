import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from larder.db.base import Base
from larder.db.models.enums import refresh_kind_enum


class RefreshRun(Base):
    __tablename__ = "refresh_runs"
    __table_args__ = (UniqueConstraint("household_id", "kind", "period_key", name="uq_refresh_runs_period"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(refresh_kind_enum(), nullable=False)
    period_key: Mapped[str] = mapped_column(Text, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
