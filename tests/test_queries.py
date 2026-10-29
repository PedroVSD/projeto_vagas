from app.services.query_service import get_all_queries, load_queries_from_yaml


def test_load_queries():
    data = load_queries_from_yaml("config/search_queries.yaml")
    assert "simple" in data
    assert "boolean" in data
    assert len(data["simple"]) >= 10
    assert len(data["boolean"]) >= 2


def test_get_all_queries():
    all_q = get_all_queries("config/search_queries.yaml")
    assert len(all_q) >= 21
    families = {q["family"] for q in all_q}
    assert "mlops" in families
    assert "data_engineering" in families
    assert "golang" in families
    # famílias booleanas por idioma
    assert any("_pt_boolean" in f for f in families)
    assert any("_en_boolean" in f for f in families)
    assert any("_es_boolean" in f for f in families)


def test_queries_target_junior_pleno_remote_hybrid():
    for q in get_all_queries("config/search_queries.yaml"):
        if "boolean" not in q["family"]:
            continue
        text = q["query"].lower()
        assert "junior" in text or "júnior" in text or "jr" in text
        assert "pleno" in text or "mid level" in text or "semi senior" in text
        assert "remote" in text or "remoto" in text or "híbrido" in text or "hybrid" in text


def test_search_profiles_countries_and_languages():
    data = load_queries_from_yaml("config/search_queries.yaml")
    profiles = data["search_profiles"]
    assert set(profiles["languages"]) == {"pt", "en", "es"}
    assert set(profiles["locations"]) == {
        "chile",
        "argentina",
        "spain",
        "portugal",
        "poland",
        "united_states",
        "canada",
    }
    assert set(profiles["seniority"]) == {"junior", "pleno"}
    assert "golang" in profiles["careers"]
