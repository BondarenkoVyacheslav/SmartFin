from django.db import models

# apps/accounts/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=200, blank=True)
    base_currency = models.CharField(max_length=10, default="USD")
    timezone = models.CharField(max_length=64, default="Europe/Riga")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SessionToken(models.Model):
    """HttpOnly-токен с хешом; хранить только digest, не сам токен."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_tokens")
    digest = models.CharField(max_length=128, unique=True, db_index=True)  # sha256 hex
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at