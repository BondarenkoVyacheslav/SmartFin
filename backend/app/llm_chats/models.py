from __future__ import annotations

from django.conf import settings
from django.db import models


class LLMChat(models.Model):
    class Mode(models.TextChoices):
        GENERAL = "GENERAL", "General"
        PORTFOLIO_ANALYSIS = "PORTFOLIO_ANALYSIS", "Portfolio analysis"
        RISK_REVIEW = "RISK_REVIEW", "Risk review"
        PERFORMANCE_REVIEW = "PERFORMANCE_REVIEW", "Performance review"
        MARKET_TRENDS = "MARKET_TRENDS", "Market trends"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_chats",
    )
    title = models.CharField(max_length=255, blank=True)
    mode = models.CharField(max_length=32, choices=Mode.choices, default=Mode.GENERAL)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"llm"."llm_chat"'
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"LLMChat({self.id})"


class ChatSettings(models.Model):
    class ContextMode(models.TextChoices):
        FULL = "FULL", "Full"
        COMPACT = "COMPACT", "Compact"
        OFF = "OFF", "Off"

    chat = models.OneToOneField(LLMChat, on_delete=models.CASCADE, related_name="settings")
    model_id = models.CharField(max_length=128)
    provider = models.CharField(max_length=64)
    temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.2)
    max_context_tokens_per_request = models.PositiveIntegerField(default=8000)
    max_output_tokens = models.PositiveIntegerField(default=1200)
    context_window_tokens = models.PositiveIntegerField(default=128000)
    system_prompt = models.TextField(blank=True, default="")
    context_mode = models.CharField(
        max_length=16,
        choices=ContextMode.choices,
        default=ContextMode.COMPACT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"llm"."llm_chat_settings"'

    def __str__(self) -> str:
        return f"ChatSettings({self.chat_id}, {self.model_id})"


class LLMMessage(models.Model):
    class Role(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        ERROR = "error", "Error"

    chat = models.ForeignKey(LLMChat, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    provider = models.CharField(max_length=64, blank=True, default="")
    model_id = models.CharField(max_length=128, blank=True, default="")
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"llm"."llm_message"'
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["chat", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"LLMMessage({self.id}, {self.role})"


class TokenUsage(models.Model):
    class UsageType(models.TextChoices):
        MESSAGE = "MESSAGE", "Message"
        DAILY = "DAILY", "Daily"
        MONTHLY = "MONTHLY", "Monthly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_token_usage",
    )
    chat = models.ForeignKey(LLMChat, on_delete=models.CASCADE, null=True, blank=True)
    message = models.ForeignKey(LLMMessage, on_delete=models.CASCADE, null=True, blank=True)
    usage_type = models.CharField(max_length=16, choices=UsageType.choices, default=UsageType.MESSAGE)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    provider = models.CharField(max_length=64, blank=True, default="")
    model_id = models.CharField(max_length=128, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    context_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"llm"."llm_token_usage"'
        indexes = [
            models.Index(fields=["user", "usage_type", "period_start"]),
            models.Index(fields=["chat", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "usage_type", "period_start"],
                name="llm_token_usage_unique_period",
                condition=models.Q(usage_type__in=["DAILY", "MONTHLY"]),
            ),
        ]


class ContextSnapshot(models.Model):
    chat = models.ForeignKey(LLMChat, on_delete=models.CASCADE, related_name="context_snapshots")
    summary_text = models.TextField()
    data = models.JSONField(default=dict)
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"llm"."llm_context_snapshot"'
        ordering = ["-created_at"]
