import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailService:
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
        ) as smtp:
            smtp.send_message(message)
