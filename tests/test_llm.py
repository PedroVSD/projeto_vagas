from unittest.mock import Mock, patch

from app.core.config import get_settings
from app.scoring.llm import LLMClassification, _parse_and_validate, get_llm_provider


def test_parse_and_validate_ok():
    raw = (
        '{"relevance_score": 80, "seniority_match": 90, "area_match": 80, '
        '"technology_match": 85, "remote_match": 100, "overall_match": 87, '
        '"recommendation": "apply", "reason": "ok", '
        '"missing_requirements": [], "matching_skills": ["Python"], "concerns": []}'
    )
    res = _parse_and_validate(raw)
    assert isinstance(res, LLMClassification)
    assert res.overall_match == 87
    assert res.recommendation == "apply"


def test_parse_and_validate_markdown():
    raw = (
        '```json\n{"relevance_score": 80, "seniority_match": 90, '
        '"area_match": 80, "technology_match": 85, "remote_match": 100, '
        '"overall_match": 87, "recommendation": "apply", "reason": "ok", '
        '"missing_requirements": [], "matching_skills": [], "concerns": []}\n```'
    )
    res = _parse_and_validate(raw)
    assert res is not None
    assert res.overall_match == 87


def test_parse_and_validate_invalid():
    assert _parse_and_validate("not json") is None
    assert _parse_and_validate('{"relevance_score": 100}') is None  # missing fields


def test_llm_provider_disabled():
    get_settings.cache_clear()
    with patch.dict("os.environ", {"LLM_PROVIDER": "disabled"}):
        get_settings.cache_clear()
        p = get_llm_provider()
        assert p.is_enabled() is False
        assert p.classify({"title": "test"}) is None
    get_settings.cache_clear()


def test_ollama_provider_mocked():
    from app.scoring.llm import OllamaProvider

    p = OllamaProvider("http://localhost:11434", "llama3.1:8b")
    fake_json = (
        '{"relevance_score": 80, "seniority_match": 90, "area_match": 80, '
        '"technology_match": 85, "remote_match": 100, "overall_match": 85, '
        '"recommendation": "apply", "reason": "boa", '
        '"missing_requirements": [], "matching_skills": ["Python"], "concerns": []}'
    )
    with patch("app.scoring.llm.httpx.Client") as mock_client:
        mock_resp = Mock()
        mock_resp.json.return_value = {"message": {"content": fake_json}}
        mock_resp.raise_for_status = Mock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp

        res = p.classify({"title": "Junior Python", "company": "X", "url": "https://example.com"})
        assert res is not None
        assert res.overall_match == 85


def test_score_service_calls_llm_when_candidate():

    from app.services.score_service import score_and_persist

    # Mock DB e Job com heuristic alta
    mock_db = Mock()
    mock_job = Mock()
    mock_job.id = 1
    mock_job.title = "Junior Data Engineer"
    mock_job.description = "Python, SQL, Airflow, Docker - remoto Brasil"
    mock_job.location = "Brasil - Remoto"
    mock_job.modality = "remoto_brasil"
    mock_job.seniority = "junior"
    mock_job.technologies = ["Python", "SQL"]
    mock_company = Mock()
    mock_company.name = "Empresa X"
    mock_job.company = mock_company
    mock_job.url = "https://example.com/1"

    # mock JobScore query -> None (não existe)
    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    mock_db.add = Mock()
    mock_db.flush = Mock()

    fake_llm = LLMClassification(
        relevance_score=80,
        seniority_match=90,
        area_match=85,
        technology_match=80,
        remote_match=100,
        overall_match=88,
        recommendation="apply",
        reason="muito relevante",
        missing_requirements=[],
        matching_skills=["Python"],
        concerns=[],
    )

    with patch("app.scoring.llm.get_llm_provider") as mock_provider_factory:
        mock_provider = Mock()
        mock_provider.is_enabled.return_value = True
        mock_provider.classify.return_value = fake_llm
        mock_provider_factory.return_value = mock_provider

        # garante threshold baixo para candidatar
        get_settings.cache_clear()
        score = score_and_persist(mock_db, mock_job)
        # llm_score deve ser preenchido
        assert score.llm_score == 88
        # final deve ser média ponderada
        assert score.heuristic_score >= 60
        assert score.final_score is not None
        mock_provider.classify.assert_called_once()


def test_score_service_no_llm_when_low_score():
    from app.services.score_service import score_and_persist

    mock_db = Mock()
    mock_job = Mock()
    mock_job.id = 2
    mock_job.title = "Senior Java"
    mock_job.description = "10+ anos Java presencial"
    mock_job.location = "Sao Paulo"
    mock_job.modality = "presencial"
    mock_job.seniority = "senior"
    mock_job.technologies = []
    mock_company = Mock()
    mock_company.name = "Corp"
    mock_job.company = mock_company
    mock_job.url = "https://example.com/2"

    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    mock_db.add = Mock()
    mock_db.flush = Mock()

    with patch("app.scoring.llm.get_llm_provider") as mock_factory:
        # se heurístico for baixo (<60), não deve chamar LLM
        mock_provider = Mock()
        mock_provider.is_enabled.return_value = True
        mock_factory.return_value = mock_provider

        score = score_and_persist(mock_db, mock_job)
        # heuristic baixo -> llm_score None, não chamou
        assert score.llm_score is None
        mock_provider.classify.assert_not_called()
