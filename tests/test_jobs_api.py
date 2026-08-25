from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_has_jobs():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/jobs" in paths
    assert "/jobs/{job_id}" in paths
    assert "/jobs/recommended" in paths


def test_docs_available():
    r = client.get("/docs")
    assert r.status_code == 200
