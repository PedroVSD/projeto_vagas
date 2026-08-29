from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
