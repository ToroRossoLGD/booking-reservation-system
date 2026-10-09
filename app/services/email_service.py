import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


class EmailService:
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        if settings.DEMO_MODE or settings.SMTP_MODE == "disabled":
            return
        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            options = {"timeout": settings.SMTP_TIMEOUT_SECONDS}
            factory = smtplib.SMTP
            if settings.SMTP_MODE == "tls":
                factory = smtplib.SMTP_SSL
                options["context"] = ssl.create_default_context()
            with factory(settings.SMTP_HOST, settings.SMTP_PORT, **options) as smtp:
                if settings.SMTP_MODE == "starttls":
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                if smtp.send_message(message):
                    raise EmailDeliveryError("Email delivery failed")
        except (OSError, smtplib.SMTPException):
            # Provider responses may include credentials, addresses or message data.
            raise EmailDeliveryError("Email delivery failed") from None
