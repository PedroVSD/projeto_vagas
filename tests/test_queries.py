from app.services.query_service import get_all_queries, load_queries_from_yaml


def test_load_queries():
    data = load_queries_from_yaml("config/search_queries.yaml")
    assert "simple" in data
    assert "boolean" in data
    assert len(data["simple"]) >= 10
    assert len(data["boolean"]) >= 2


def test_get_all_queries():
    all_q = get_all_queries("config/search_queries.yaml")
    assert len(all_q) == 21  # 17 simple + 4 boolean
    families = {q["family"] for q in all_q}
    assert "mlops" in families
    assert "data_engineering" in families
