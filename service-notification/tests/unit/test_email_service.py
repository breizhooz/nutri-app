"""Unit tests for EmailService."""

from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService


class TestEmailServiceBuildMessage:
    """Tests for the _build_mfa_message static method."""

    @pytest.mark.unit
    def test_message_has_correct_recipient(self) -> None:
        """The To header matches the given recipient."""
        msg = EmailService._build_mfa_message("user@test.com", "123456")
        assert msg["To"] == "user@test.com"

    @pytest.mark.unit
    def test_message_subject_contains_nutri(self) -> None:
        """Subject line references NutriApp."""
        msg = EmailService._build_mfa_message("user@test.com", "999999")
        assert "NutriApp" in msg["Subject"]

    @pytest.mark.unit
    def test_message_contains_code_in_text_part(self) -> None:
        """Plain-text payload includes the OTP code."""
        msg = EmailService._build_mfa_message("user@test.com", "654321")
        payloads = [p.get_payload() for p in msg.get_payload()]
        assert any("654321" in str(p) for p in payloads)

    @pytest.mark.unit
    def test_message_is_multipart(self) -> None:
        """Message is multipart/alternative with text and HTML parts."""
        msg = EmailService._build_mfa_message("user@test.com", "111111")
        assert isinstance(msg, MIMEMultipart)
        assert len(msg.get_payload()) == 2


class TestEmailServiceSendMfaCode:
    """Tests for the send_mfa_code static method."""

    @pytest.mark.unit
    async def test_send_returns_true_on_success(self) -> None:
        """send_mfa_code returns True when aiosmtplib.send succeeds."""
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service.aiosmtplib.send", new=AsyncMock()) as mock_send,
        ):
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM = "noreply@test.com"
            mock_settings.SMTP_USE_TLS = False
            result = await EmailService.send_mfa_code("dest@test.com", "123456")
        assert result is True
        mock_send.assert_called_once()

    @pytest.mark.unit
    async def test_send_returns_false_on_smtp_error(self) -> None:
        """send_mfa_code returns False when aiosmtplib raises."""
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch(
                "app.services.email_service.aiosmtplib.send",
                new=AsyncMock(side_effect=Exception("SMTP error")),
            ),
        ):
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = ""
            mock_settings.SMTP_PASSWORD = ""
            mock_settings.SMTP_FROM = "noreply@test.com"
            mock_settings.SMTP_USE_TLS = False
            result = await EmailService.send_mfa_code("dest@test.com", "123456")
        assert result is False

    @pytest.mark.unit
    async def test_send_returns_false_when_smtp_host_not_configured(self) -> None:
        """send_mfa_code returns False and skips send when SMTP_HOST is empty."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            result = await EmailService.send_mfa_code("dest@test.com", "123456")
        assert result is False