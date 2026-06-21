from django.conf import settings
from django.core.mail import EmailMessage


def send_contact_notification(*, name: str, email: str, subject: str, message: str) -> None:
    inbox = settings.CONTACT_INBOX_EMAIL
    email_subject = f"[communiB Contact] {subject}"
    body = (
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject}\n\n"
        f"{message}"
    )
    msg = EmailMessage(
        subject=email_subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[inbox],
        reply_to=[email],
    )
    msg.send(fail_silently=False)
