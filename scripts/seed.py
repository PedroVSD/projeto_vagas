"""Seed mínimo para testar Fase 1."""
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.job import Job
from app.models.job_source import JobSource

db = SessionLocal()
try:
    # Company
    if not db.query(Company).filter_by(name="Empresa Demo").first():
        c = Company(name="Empresa Demo", website="https://example.com")
        db.add(c)
        db.commit()
        print(f"Company criada id={c.id}")
    else:
        c = db.query(Company).filter_by(name="Empresa Demo").first()
        print(f"Company já existe id={c.id}")

    # Source
    if not db.query(JobSource).filter_by(name="demo").first():
        s = JobSource(name="demo", enabled=True, config={"demo": True})
        db.add(s)
        db.commit()
        print(f"JobSource criado id={s.id}")
    else:
        s = db.query(JobSource).filter_by(name="demo").first()
        print(f"JobSource já existe id={s.id}")

    # Job de exemplo (se não existir)
    fp = "demo-fingerprint-123"
    if not db.query(Job).filter_by(fingerprint=fp).first():
        job = Job(
            fingerprint=fp,
            title="Junior Data Engineer",
            company_id=c.id,
            source_id=s.id,
            url="https://example.com/jobs/1",
            description="Vaga Júnior com Python, SQL, Airflow e Docker - remoto",
            location="Brasil",
            modality="remoto",
            seniority="junior",
            technologies=["Python", "SQL", "Airflow", "Docker"],
            raw_payload={"source": "seed"},
        )
        db.add(job)
        db.commit()
        print(f"Job criado id={job.id}")
    else:
        print("Job demo já existe")

    print("Seed OK -", db.query(Job).count(), "jobs")
finally:
    db.close()
