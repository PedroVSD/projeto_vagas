from datetime import datetime

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    title: str
    url: str
    description: str | None = None
    location: str | None = None
    modality: str | None = None
    seniority: str | None = None
    technologies: list[str] | None = None


class JobCreate(JobBase):
    fingerprint: str
    company_id: int | None = None
    source_id: int | None = None
    raw_payload: dict | None = None


class JobResponse(JobBase):
    id: int
    fingerprint: str
    company_id: int | None
    source_id: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int = Field(description="Total de vagas retornadas")
