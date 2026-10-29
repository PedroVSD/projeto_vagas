from app.scoring.filters import is_relevant
from app.scoring.heuristic import classify_score, score_job


def test_junior_data_engineer_excelente():
    job = {
        "title": "Junior Data Engineer",
        "description": "Python, SQL, Airflow, Docker - remoto Brasil",
        "location": "Brasil - Remoto",
        "modality": "remoto_brasil",
        "seniority": "junior",
        "technologies": ["Python", "SQL", "Docker", "Airflow"],
    }
    res = score_job(job)
    assert res["final_score"] >= 90
    assert res["classification"] == "excelente"


def test_estagio_fora_do_perfil():
    job = {
        "title": "Estágio MLOps",
        "description": "Python Docker Kubernetes MLflow AWS remoto",
        "location": "Remoto",
        "modality": "remoto",
        "seniority": "intern",
        "technologies": ["Python", "Docker", "Kubernetes", "MLflow", "AWS"],
    }
    assert is_relevant(job)[0] is False


def test_senior_ignorar():
    job = {
        "title": "Senior Data Engineer",
        "description": "8+ anos experiencia, presencial Sao Paulo, Java",
        "location": "Sao Paulo Presencial",
        "modality": "presencial",
        "seniority": "senior",
        "technologies": [],
    }
    res = score_job(job)
    assert res["final_score"] < 45
    assert res["classification"] == "ignorar"


def test_tech_cap():
    # Muitas techs não deve inflar além do cap 25
    job = {
        "title": "Junior Python Developer",
        "description": "Python Go Docker K8s AWS GCP Azure Airflow Spark Databricks MLflow",
        "location": "Remoto",
        "modality": "remoto",
        "seniority": "junior",
        "technologies": [
            "Python",
            "Go",
            "Docker",
            "Kubernetes",
            "AWS",
            "GCP",
            "Azure",
            "Airflow",
            "Spark",
            "Databricks",
            "MLflow",
            "SQL",
            "Kafka",
        ],
    }
    res = score_job(job)
    assert res["tech_breakdown"]["points"] == 25  # cap
    assert res["final_score"] <= 100


def test_classify_thresholds():
    assert classify_score(95) == "excelente"
    assert classify_score(80) == "muito_relevante"
    assert classify_score(65) == "relevante"
    assert classify_score(50) == "talvez_relevante"
    assert classify_score(20) == "ignorar"


def test_is_relevant_filter():
    assert (
        is_relevant(
            {"title": "Junior Python", "description": "Python", "technologies": ["Python"]}
        )[0]
        is True
    )
    assert (
        is_relevant({"title": "Vendas", "description": "vendas marketing", "technologies": []})[0]
        is False
    )
    assert (
        is_relevant(
            {"title": "Senior", "description": "exige 10+ anos", "technologies": ["Python"]}
        )[0]
        is False
    )


def test_filter_apenas_junior_pleno():
    assert is_relevant({"title": "Pleno Data Engineer", "seniority": "pleno"})[0] is True
    assert is_relevant({"title": "Estágio Data Engineer", "seniority": "intern"})[0] is False
    assert is_relevant({"title": "Senior Data Engineer", "seniority": "senior"})[0] is False
    assert is_relevant({"title": "Staff Engineer", "seniority": "staff"})[0] is False


def test_filter_apenas_remoto_ou_hibrido():
    assert is_relevant({"title": "Pleno Python", "modality": "remoto"})[0] is True
    assert is_relevant({"title": "Pleno Python", "modality": "hibrido"})[0] is True
    assert is_relevant({"title": "Pleno Python", "modality": "presencial"})[0] is False


def test_pleno_score_relevante():
    job = {
        "title": "Pleno Data Engineer",
        "description": "Python, SQL, Docker - remoto",
        "location": "Chile",
        "modality": "remoto",
        "seniority": "pleno",
        "technologies": ["Python", "SQL", "Docker"],
    }
    res = score_job(job)
    assert res["final_score"] >= 70
