from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    class Code(models.TextChoices):
        BASE = 'base', 'Base'
        PREMIUM = 'premium', 'Premium'

    code = models.CharField(max_length=32, unique=True, choices=Code.choices)
    name = models.CharField(max_length=120)
    features = models.JSONField(default=list)
    limits = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRIALING = 'trialing', 'Trialing'
        PAST_DUE = 'past_due', 'Past due'
        CANCELED = 'canceled', 'Canceled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    provider = models.CharField(max_length=32, default='manual')
    provider_subscription_id = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id}:{self.plan.code}:{self.status}"

    def is_active(self, now=None):
        if self.status != self.Status.ACTIVE:
            return False
        if self.current_period_end is None:
            return True
        now = now or timezone.now()
        return self.current_period_end > now
