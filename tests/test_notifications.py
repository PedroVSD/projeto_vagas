from unittest.mock import Mock, patch

from app.notifications.formatting import format_job_message
from app.notifications.service import should_notify


def test_format_job_message():
    job = {
        "title": "Junior Data Engineer",
        "company": "Empresa X",
        "url": "https://example.com/jobs/1",
        "location": "Brasil - Remoto",
        "modality": "remoto_brasil",
        "seniority": "junior",
        "technologies": ["Python", "SQL", "Airflow"],
        "first_seen_at": "2026-08-24",
    }
    score = {
        "final_score": 87,
        "classification": "muito_relevante",
        "area_breakdown": {"area": "data_engineering"},
        "penalties": {},
    }
    subject, body = format_job_message(job, score)
    assert "Junior Data Engineer" in subject
    assert "Empresa X" in subject
    assert "87/100" in subject
    assert "Candidatura: https://example.com/jobs/1" in body
    assert "Python" in body


def test_should_notify_thresholds():
    assert should_notify({"final_score": 95})[0] is True
    assert should_notify({"final_score": 95})[1] == "immediate"
    assert should_notify({"final_score": 70})[0] is True
    assert should_notify({"final_score": 70})[1] == "digest"
    assert should_notify({"final_score": 30})[0] is False


def test_telegram_disabled_without_config():
    from app.notifications.telegram import TelegramProvider

    p = TelegramProvider(bot_token=None, chat_id=None)
    # força disabled
    p.bot_token = None
    p.chat_id = None
    assert p.is_enabled() is False
    assert p.send({"title": "test"}) is False


def test_email_disabled_without_config():
    from app.notifications.email import EmailProvider

    p = EmailProvider(smtp_host=None, smtp_to=None, smtp_from=None)
    p.smtp_host = None
    assert p.is_enabled() is False
    assert p.send({"title": "test"}) is False


def test_telegram_send_mocked():
    from app.notifications.telegram import TelegramProvider

    p = TelegramProvider(bot_token="fake_token", chat_id="123")
    assert p.is_enabled() is True
    with patch("app.notifications.telegram.httpx.Client") as mock_client:
        mock_resp = Mock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = Mock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        payload = {
            "title": "Junior Test",
            "company": "Demo",
            "url": "https://example.com",
            "technologies": ["Python"],
            "score": {
                "final_score": 90,
                "classification": "excelente",
                "area_breakdown": {"area": "mlops"},
                "penalties": {},
            },
        }
        assert p.send(payload) is True


def test_email_send_mocked():
    from app.notifications.email import EmailProvider

    p = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_from="from@example.com",
        smtp_to="to@example.com",
        smtp_username="user",
        smtp_password="pass",
    )
    assert p.is_enabled() is True
    with patch("app.notifications.email.smtplib.SMTP") as mock_smtp:
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        payload = {
            "title": "Junior Test",
            "company": "Demo",
            "url": "https://example.com",
            "technologies": ["Python"],
            "score": {
                "final_score": 90,
                "classification": "excelente",
                "area_breakdown": {},
                "penalties": {},
            },
        }
        assert p.send(payload) is True
        mock_server.send_message.assert_called_once()


def test_notify_job_creates_notification_mocked_db():
    from app.notifications.service import notify_job

    # Mock DB e Job
    mock_db = Mock()
    # query chain para exists check -> None (não existe)
    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    mock_db.flush = Mock()
    mock_db.commit = Mock()
    mock_db.add = Mock()

    mock_job = Mock()
    mock_job.id = 1
    mock_job.title = "Junior Data Engineer"
    mock_job.url = "https://example.com/1"
    mock_job.location = "Brasil"
    mock_job.modality = "remoto"
    mock_job.seniority = "junior"
    mock_job.technologies = ["Python"]
    mock_job.description = "desc"
    mock_job.first_seen_at = "2026-08-24"
    mock_company = Mock()
    mock_company.name = "Empresa X"
    mock_job.company = mock_company

    score = {
        "final_score": 85,
        "classification": "muito_relevante",
        "area_breakdown": {"area": "data_engineering"},
        "penalties": {},
    }

    # Mock provider
    mock_provider = Mock()
    mock_provider.name = "telegram"
    mock_provider.send.return_value = True
    mock_provider.chat_id = "123"

    result = notify_job(mock_db, mock_job, score, providers=[mock_provider])
    assert len(result) == 1
    mock_db.add.assert_called()
    mock_provider.send.assert_called_once()
