import smtplib
import ssl
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.services.email_service import EmailDeliveryError, EmailService


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "private-password")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.send_message.return_value = {}
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", factory)
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", factory)
    return factory, client


def test_starttls_verifies_certificate_before_authenticating(monkeypatch, smtp):
    factory, client = smtp
    monkeypatch.setattr(settings, "SMTP_MODE", "starttls")
    EmailService().send_email("guest@example.com", "Subject", "Body")
    assert [call[0] for call in client.method_calls] == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "send_message",
    ]
    context = client.starttls.call_args.kwargs["context"]
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert factory.call_args.kwargs["timeout"] == settings.SMTP_TIMEOUT_SECONDS


def test_tls_uses_verified_context_without_starttls(monkeypatch, smtp):
    factory, client = smtp
    monkeypatch.setattr(settings, "SMTP_MODE", "tls")
    EmailService().send_email("guest@example.com", "Subject", "Body")
    assert factory.call_args.kwargs["context"].verify_mode == ssl.CERT_REQUIRED
    client.starttls.assert_not_called()
    client.login.assert_called_once_with("smtp-user", "private-password")


def test_starttls_failure_never_falls_back_to_plain_auth(monkeypatch, smtp):
    _, client = smtp
    monkeypatch.setattr(settings, "SMTP_MODE", "starttls")
    client.starttls.side_effect = smtplib.SMTPNotSupportedError("private-password")
    with pytest.raises(EmailDeliveryError, match="Email delivery failed") as error:
        EmailService().send_email("guest@example.com", "Subject", "Body")
    assert "private-password" not in str(error.value)
    client.login.assert_not_called()
    client.send_message.assert_not_called()


def test_disabled_mail_never_connects(monkeypatch, smtp):
    factory, _ = smtp
    monkeypatch.setattr(settings, "SMTP_MODE", "disabled")
    EmailService().send_email("guest@example.com", "Subject", "Body")
    factory.assert_not_called()
