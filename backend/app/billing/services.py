from django.utils import timezone

from .models import Subscription


def get_active_subscription(user):
    if user is None or not user.is_authenticated:
        return None
    now = timezone.now()
    subscription = (
        Subscription.objects.select_related('plan')
        .filter(user=user, status=Subscription.Status.ACTIVE)
        .order_by('-current_period_end', '-created_at')
        .first()
    )
    if subscription is None:
        return None
    if subscription.current_period_end and subscription.current_period_end <= now:
        return None
    return subscription


def has_feature(user, feature_code):
    if user is None or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    subscription = get_active_subscription(user)
    if subscription is None:
        return False
    return feature_code in (subscription.plan.features or [])


def get_entitlements(user):
    subscription = get_active_subscription(user)
    if subscription is None:
        return []
    return list(subscription.plan.features or [])


def get_plan_code(user):
    subscription = get_active_subscription(user)
    if subscription is None:
        return None
    return subscription.plan.code
