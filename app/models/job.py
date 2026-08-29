from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.job_score import JobScore
    from app.models.job_source import JobSource
    from app.models.notification import Notification


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_sources.id"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modality: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # remoto, hibrido, presencial
    seniority: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # intern, junior, pleno...
    technologies: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="jobs")
    source: Mapped[JobSource] = relationship(back_populates="jobs")
    score: Mapped[JobScore] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
