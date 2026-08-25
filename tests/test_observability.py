from unittest.mock import Mock, patch


def test_metrics_endpoint_no_db():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "job_finder" in r.text or "error" in r.text


def test_observability_endpoint_mocked():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    # mock get_current_stats to avoid DB
    with patch("app.core.metrics.get_current_stats") as mock_stats:
        mock_stats.return_value = {
            "jobs_total": 10,
            "jobs_scored": 8,
            "notifications_sent": 2,
            "notifications_failed": 0,
            "notifications_pending": 1,
            "by_classification": {"excelente": 2, "muito_relevante": 3, "relevante": 3, "talvez_relevante": 1, "ignorar": 1},
            "recent_runs": [],
        }
        r = c.get("/observability")
        assert r.status_code == 200
        assert r.json()["jobs_total"] == 10


def test_health_detailed():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "db" in data
    assert "llm" in data
    assert "scheduler" in data
    assert "notifications" in data


def test_metrics_prometheus_format():
    from app.core.metrics import prometheus_format

    stats = {
        "jobs_total": 5,
        "jobs_scored": 5,
        "notifications_sent": 2,
        "notifications_failed": 1,
        "by_classification": {"excelente": 1, "muito_relevante": 1, "relevante": 1, "talvez_relevante": 1, "ignorar": 1},
    }
    out = prometheus_format(stats)
    assert "job_finder_jobs_total 5" in out
    assert 'job_finder_by_classification{classification="excelente"} 1' in out


def test_record_run():
    from app.core.metrics import get_history, record_run

    record_run({"collected": 10, "new": 5, "elapsed_s": 1.2})
    hist = get_history(1)
    assert hist[-1]["collected"] == 10
