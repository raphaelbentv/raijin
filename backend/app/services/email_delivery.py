from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import get_settings


class EmailDeliveryError(RuntimeError):
    pass


async def send_transactional_email(*, to_email: str, subject: str, text: str, html: str) -> bool:
    settings = get_settings()

    if settings.resend_api_key:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [to_email],
                    "subject": subject,
                    "text": text,
                    "html": html,
                },
            )
        if response.status_code >= 400:
            raise EmailDeliveryError(f"resend_failed:{response.status_code}")
        return True

    if settings.smtp_host:
        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True

    return False
