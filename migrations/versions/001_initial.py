"""initial - cria tabelas base da Fase 1

Revision ID: 001
Revises:
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=True)

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_sources_name"), "job_sources", ["name"], unique=True)

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("family", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source_filter", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_search_queries_family"), "search_queries", ["family"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("min_score_threshold", sa.Integer(), nullable=False),
        sa.Column("notify_channels", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False),
        sa.Column("digest_time", sa.String(length=10), nullable=False),
        sa.Column("immediate_threshold", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("modality", sa.String(length=50), nullable=True),
        sa.Column("seniority", sa.String(length=50), nullable=True),
        sa.Column("technologies", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_company_id"), "jobs", ["company_id"], unique=False)
    op.create_index(op.f("ix_jobs_fingerprint"), "jobs", ["fingerprint"], unique=True)
    op.create_index(op.f("ix_jobs_source_id"), "jobs", ["source_id"], unique=False)
    op.create_index(op.f("ix_jobs_title"), "jobs", ["title"], unique=False)
    op.create_index("ix_jobs_url", "jobs", ["url"], unique=True)

    op.create_table(
        "job_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("heuristic_score", sa.Integer(), nullable=True),
        sa.Column("llm_score", sa.Integer(), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("seniority_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("area_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tech_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("modality_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("penalties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("classification", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_scores_final_score"), "job_scores", ["final_score"], unique=False)
    op.create_index(op.f("ix_job_scores_job_id"), "job_scores", ["job_id"], unique=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=100), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_job_id"), "notifications", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_job_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_job_scores_job_id"), table_name="job_scores")
    op.drop_index(op.f("ix_job_scores_final_score"), table_name="job_scores")
    op.drop_table("job_scores")
    op.drop_index("ix_jobs_url", table_name="jobs")
    op.drop_index(op.f("ix_jobs_title"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_source_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_fingerprint"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_company_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("user_preferences")
    op.drop_index(op.f("ix_search_queries_family"), table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_index(op.f("ix_job_sources_name"), table_name="job_sources")
    op.drop_table("job_sources")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_table("companies")
