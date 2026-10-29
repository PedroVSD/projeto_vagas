from app.services.normalization import extract_modality, extract_seniority, extract_technologies


def test_extract_technologies():
    text = "Vaga Junior com Python, SQL, Docker, Kubernetes e AWS - remoto"
    techs = extract_technologies(text)
    assert "Python" in techs
    assert "SQL" in techs
    assert "Docker" in techs
    assert "Kubernetes" in techs
    assert "AWS" in techs


def test_extract_seniority_junior():
    assert extract_seniority("Junior Data Engineer", "Vaga junior") == "junior"
    assert extract_seniority("Estágio MLOps", "") == "intern"
    assert extract_seniority("Senior Data Engineer", "") == "senior"


def test_extract_seniority_espanhol():
    assert extract_seniority("Desarrollador Junior Golang", "") == "junior"
    assert extract_seniority("Ingeniero de Datos Semi Senior", "") == "pleno"
    assert extract_seniority("Desarrollador Pleno", "") == "pleno"
    assert extract_seniority("Pasantía Data Science", "") == "intern"


def test_extract_seniority_none():
    assert extract_seniority("Data Engineer", "Experiência com Python") is None


def test_extract_modality():
    assert extract_modality("Brasil - Remoto", "trabalho remoto") == "remoto_brasil"
    assert extract_modality("Remoto", "") == "remoto"
    assert extract_modality("Híbrido - São Paulo", "") == "hibrido"
    assert extract_modality("Presencial - São Paulo", "") == "presencial"
    assert extract_modality(None, "100% remoto") == "remoto"


def test_extract_modality_espanhol():
    assert extract_modality("Chile - Remoto", "") == "remoto_brasil"
    assert extract_modality(None, "Trabajo remoto") == "remoto"
    assert extract_modality("Modalidad híbrida", "") == "hibrido"
    assert extract_modality("Teletrabajo", "") == "remoto"
