from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'current_period_end', 'provider')
    list_filter = ('status', 'provider', 'plan')
    search_fields = ('user__email', 'user__username', 'provider_subscription_id')
