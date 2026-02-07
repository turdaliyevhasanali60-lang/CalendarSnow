# users/utils.py
import secrets
from django.conf import settings
from django.core.mail import send_mail

def generate_otp() -> str:
    length = getattr(settings, "EMAIL_OTP_LENGTH", 6)
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))

def send_otp_email(to_email: str, otp: str) -> None:
    ttl_min = getattr(settings, "EMAIL_OTP_TTL_SECONDS", 600) // 60

    subject = "Your verification code"
    message = (
        "Use this code to verify your email address:\n\n"
        f"{otp}\n\n"
        f"This code expires in {ttl_min} minutes.\n"
        "If you didn’t request this, you can ignore this message."
    )

    # Django send_mail rasmiy funksiyasi orqali yuboriladi.  [oai_citation:6‡Django Project](https://docs.djangoproject.com/en/6.0/topics/email/)
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )