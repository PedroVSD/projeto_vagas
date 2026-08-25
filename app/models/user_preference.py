from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    min_score_threshold: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notify_channels: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_time: Mapped[str] = mapped_column(String(10), default="08:00", nullable=False)
    immediate_threshold: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
