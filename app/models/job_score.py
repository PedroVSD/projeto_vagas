from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    heuristic_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    seniority_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    area_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tech_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    modality_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    penalties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)  # excelente, muito_relevante...

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    job: Mapped["Job"] = relationship(back_populates="score")  # type: ignore[name-defined]
