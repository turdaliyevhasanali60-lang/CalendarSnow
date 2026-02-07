# users/models.py
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class EmailOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_otp")
    code = models.CharField(max_length=10)
    created_at = models.DateTimeField(default=timezone.now)  # reset when resending
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self):  # Ensures old codes cannot be used.
        ttl = getattr(settings, "EMAIL_OTP_TTL_SECONDS", 600)
        return timezone.now() > self.created_at + timezone.timedelta(seconds=ttl)

    def can_resend(self):
        cooldown = getattr(settings, "EMAIL_OTP_RESEND_COOLDOWN", 60)
        if not self.last_sent_at:
            return True
        return timezone.now() > self.last_sent_at + timezone.timedelta(seconds=cooldown)

    def __str__(self):
        return f"EmailOTP(user={self.user_id})"

    def cooldown_seconds(self) -> int:
        return int(getattr(settings, "EMAIL_OTP_RESEND_COOLDOWN", 60))

    def resend_remaining_seconds(self) -> int:
        """
        If resending is not allowed yet, returns how many seconds remain.
        Otherwise returns 0.
        """
        if not self.last_sent_at:
            return 0
        remaining = (self.last_sent_at + timezone.timedelta(
            seconds=self.cooldown_seconds()) - timezone.now()).total_seconds()
        return max(0, int(remaining))


from django.conf import settings
from django.db import models

class Task(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    date = models.DateField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "created_at"]

    def __str__(self):
        return f"{self.title} ({self.user})"