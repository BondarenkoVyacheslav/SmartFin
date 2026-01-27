from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db import models
from django.utils import timezone

from app.billing.models import Subscription
from app.llm_chats.models import TokenUsage, LLMMessage


@dataclass(frozen=True)
class TokenLimits:
    context_tokens_remaining: int
    user_tokens_remaining_daily: int | None
    user_tokens_remaining_monthly: int | None


def estimate_tokens(text: str) -> int:
    """Rough token estimator (no provider-specific tokenizer)."""
    if not text:
        return 0
    # 1 token ~= 4 characters for Latin text (very rough).
    return max(1, math.ceil(len(text) / 4))


def estimate_message_tokens(messages: list[dict[str, str]]) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("role", ""))
        total += estimate_tokens(msg.get("content", ""))
    return total


def _get_active_subscription(user):
    return (
        Subscription.objects.filter(user=user, status=Subscription.Status.ACTIVE)
        .order_by("-created_at")
        .select_related("plan")
        .first()
    )


def get_user_token_budgets(user) -> tuple[int, int]:
    subscription = _get_active_subscription(user)
    if not subscription or not subscription.plan:
        return 0, 0
    limits = subscription.plan.limits or {}
    daily = int(limits.get("llm_tokens_daily", 0))
    monthly = int(limits.get("llm_tokens_monthly", 0))
    return daily, monthly


def _sum_tokens_for_period(user, period_start: date, period_end: date) -> int:
    usage = TokenUsage.objects.filter(
        user=user,
        usage_type=TokenUsage.UsageType.MESSAGE,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).aggregate(total=models.Sum("total_tokens"))
    return int(usage["total"] or 0)


def get_tokens_used_daily(user, day: date | None = None) -> int:
    day = day or timezone.now().date()
    aggregate = TokenUsage.objects.filter(
        user=user,
        usage_type=TokenUsage.UsageType.DAILY,
        period_start=day,
    ).first()
    if aggregate:
        return aggregate.total_tokens
    return _sum_tokens_for_period(user, day, day)


def get_tokens_used_monthly(user, day: date | None = None) -> int:
    day = day or timezone.now().date()
    period_start = day.replace(day=1)
    period_end = day
    aggregate = TokenUsage.objects.filter(
        user=user,
        usage_type=TokenUsage.UsageType.MONTHLY,
        period_start=period_start,
    ).first()
    if aggregate:
        return aggregate.total_tokens
    return _sum_tokens_for_period(user, period_start, period_end)


def calculate_token_limits(user, context_window: int, context_used: int) -> TokenLimits:
    daily_budget, monthly_budget = get_user_token_budgets(user)
    daily_used = get_tokens_used_daily(user)
    monthly_used = get_tokens_used_monthly(user)
    context_remaining = max(0, context_window - context_used)
    daily_remaining = max(0, daily_budget - daily_used) if daily_budget else None
    monthly_remaining = max(0, monthly_budget - monthly_used) if monthly_budget else None
    return TokenLimits(
        context_tokens_remaining=context_remaining,
        user_tokens_remaining_daily=daily_remaining,
        user_tokens_remaining_monthly=monthly_remaining,
    )


def record_token_usage(
    *,
    user,
    chat,
    message: LLMMessage,
    provider: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    context_tokens: int,
) -> None:
    total_tokens = prompt_tokens + completion_tokens
    now = timezone.now()
    day = now.date()
    month_start = now.replace(day=1).date()

    with transaction.atomic():
        TokenUsage.objects.create(
            user=user,
            chat=chat,
            message=message,
            usage_type=TokenUsage.UsageType.MESSAGE,
            provider=provider,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            context_tokens=context_tokens,
        )

        _bump_aggregate(user, day, TokenUsage.UsageType.DAILY, total_tokens)
        _bump_aggregate(user, month_start, TokenUsage.UsageType.MONTHLY, total_tokens)


def _bump_aggregate(user, period_start: date, usage_type: str, tokens: int) -> None:
    aggregate = (
        TokenUsage.objects.select_for_update()
        .filter(user=user, usage_type=usage_type, period_start=period_start)
        .first()
    )
    if not aggregate:
        aggregate = TokenUsage.objects.create(
            user=user,
            usage_type=usage_type,
            period_start=period_start,
            period_end=period_start,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            context_tokens=0,
        )
    aggregate.total_tokens += tokens
    aggregate.save(update_fields=["total_tokens"])
