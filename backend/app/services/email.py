import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY


def send_email(to: str, subject: str, html: str) -> dict:
    return resend.Emails.send({
        "from": "Polyclinic <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "html": html,
    })
