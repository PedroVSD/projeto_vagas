from unittest.mock import Mock, patch


def test_run_pipeline_mocked():
    from app.workers.runner import run_pipeline

    with (
        patch("app.workers.runner.ingest_all") as mock_ingest,
        patch("app.workers.runner.SessionLocal") as mock_session_cls,
    ):
        mock_db = Mock()
        mock_session_cls.return_value = mock_db
        # mock ingest_all retorna métricas
        mock_ingest.return_value = [
            {"source": "demo", "collected": 3, "new": 3, "duplicates": 0, "errors": 0}
        ]
        # garantir que mock_db não quebre errors_by_source
        # mock Notification count
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 1
        mock_db.query.return_value = mock_query

        metrics = run_pipeline()
        assert metrics["collected"] == 3
        assert metrics["new"] == 3
        assert "elapsed_s" in metrics


def test_run_digest_no_provider():
    from app.workers.runner import run_digest

    with (
        patch("app.workers.runner.SessionLocal") as mock_session_cls,
        patch("app.notifications.service.get_enabled_providers", return_value=[]),
        patch("app.notifications.service.build_digest") as mock_digest,
    ):
        mock_db = Mock()
        mock_session_cls.return_value = mock_db
        mock_digest.return_value = {
            "total": 10,
            "highly_relevant": 2,
            "relevant": 3,
            "discarded": 5,
            "top": [],
        }

        result = run_digest()
        assert result["total"] == 10


def test_worker_api_status():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/worker/status")
    assert r.status_code == 200
    assert "scheduler_enabled" in r.json()
    assert "interval_minutes" in r.json()


def test_scheduler_config():
    from app.core.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.scheduler_interval_minutes >= 1
    assert isinstance(s.scheduler_enabled, bool)


def test_run_pipeline_via_api_mocked():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    with patch(
        "app.workers.runner.ingest_all",
        return_value=[{"source": "demo", "collected": 1, "new": 1, "duplicates": 0, "errors": 0}],
    ):
        with patch("app.workers.runner.SessionLocal") as mock_session_cls:
            mock_db = Mock()
            mock_session_cls.return_value = mock_db
            mock_query = Mock()
            mock_query.filter.return_value.count.return_value = 0
            mock_db.query.return_value = mock_query

            r = c.post("/worker/run")
            assert r.status_code == 200
            assert "collected" in r.json()
