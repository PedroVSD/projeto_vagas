from unittest.mock import Mock, patch

from app.sources import DemoSource, get_source_by_name
from app.sources.arbeitnow import ArbeitnowSource


def test_demo_source_fetch_and_normalize():
    src = DemoSource()
    raws = src.fetch_jobs()
    assert len(raws) == 3
    norms = [src.normalize_job(r) for r in raws]
    # Junior deve ter seniority junior, remoto, techs
    j1 = norms[0]
    assert j1.seniority == "junior"
    assert j1.modality in ("remoto", "remoto_brasil")
    assert "Python" in (j1.technologies or [])
    assert j1.fingerprint is not None
    assert len(j1.fingerprint) == 64
    # Senior deve ser detectado
    assert norms[2].seniority == "senior"


def test_demo_fingerprint_dedup():
    src = DemoSource()
    raws = src.fetch_jobs()
    n1 = src.normalize_job(raws[0])
    n2 = src.normalize_job(raws[0])
    assert n1.fingerprint == n2.fingerprint


def test_registry():
    # demo removido do DEFAULT_SOURCES (mock só p/ testes unitários, não produção)
    assert get_source_by_name("arbeitnow") is not None
    assert get_source_by_name("gupy") is not None
    assert get_source_by_name("inexistente") is None
    # DemoSource ainda importável mas não no registry padrão
    from app.sources.demo import DemoSource

    assert DemoSource().name == "demo"


def test_arbeitnow_normalize_mocked():
    # Mock API response sem chamar rede
    fake_job = {
        "slug": "test-123",
        "company_name": "Test Co",
        "title": "Junior Python Developer",
        "description": "Python, Docker, remote work",
        "url": "https://www.arbeitnow.com/jobs/test-123",
        "location": "Berlin, Remote",
        "tags": ["python", "docker"],
        "remote": True,
    }
    src = ArbeitnowSource()
    with patch("app.sources.arbeitnow.httpx.Client") as mock_client:
        mock_resp = Mock()
        mock_resp.json.return_value = {"data": [fake_job]}
        mock_resp.raise_for_status = Mock()
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

        raws = src.fetch_jobs()
        assert len(raws) == 1
        assert raws[0].title == "Junior Python Developer"
        norm = src.normalize_job(raws[0])
        assert norm.seniority == "junior"
        assert "Python" in (norm.technologies or [])
        assert norm.fingerprint is not None


def test_arbeitnow_fetch_failure_returns_empty():
    src = ArbeitnowSource()
    with patch("app.sources.arbeitnow.httpx.Client", side_effect=Exception("network error")):
        raws = src.fetch_jobs()
        assert raws == []
