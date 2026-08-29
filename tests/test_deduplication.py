from app.services.deduplication import build_fingerprint


def test_fingerprint_stable():
    fp1 = build_fingerprint(
        "Empresa X", "Junior Data Engineer", "Remoto", "https://example.com/1", "desc"
    )
    fp2 = build_fingerprint(
        "Empresa X", "Junior Data Engineer", "Remoto", "https://example.com/1", "desc"
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_different_url():
    fp1 = build_fingerprint(
        "Empresa X", "Junior Data Engineer", "Remoto", "https://example.com/1", "desc"
    )
    fp2 = build_fingerprint(
        "Empresa X", "Junior Data Engineer", "Remoto", "https://example.com/2", "desc"
    )
    assert fp1 != fp2


def test_fingerprint_case_insensitive():
    fp1 = build_fingerprint(
        "Empresa X", "Junior Data Engineer", "Remoto", "https://example.com/1", "desc"
    )
    fp2 = build_fingerprint(
        "empresa x", "junior data engineer", "remoto", "https://example.com/1", "desc"
    )
    assert fp1 == fp2


def test_fingerprint_accent_insensitive():
    fp1 = build_fingerprint(
        "Empresa São Paulo", "Estágio", "São Paulo", "https://example.com/1", None
    )
    fp2 = build_fingerprint(
        "Empresa Sao Paulo", "Estagio", "Sao Paulo", "https://example.com/1", None
    )
    assert fp1 == fp2
