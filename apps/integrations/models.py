# apps/integrations/models.py
from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField


class Integration(models.Model):
    """
    integrations.integration
    """
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="integrations",
    )
    provider = models.TextField()                      # text NOT NULL
    display_name = models.TextField()                  # text NOT NULL
    status = models.TextField(default="active")        # text NOT NULL DEFAULT 'active'
    credentials_encrypted = models.TextField()         # text NOT NULL
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # DEFAULT now()
    updated_at = models.DateTimeField(auto_now=True)      # DEFAULT now()

    class Meta:
        db_table = 'integrations"."integration'
        managed = True
        constraints = [
            # UNIQUE (user_id, provider, display_name)
            models.UniqueConstraint(
                fields=["user", "provider", "display_name"],
                name="integration_user_id_provider_display_name_key",
            ),
        ]

    def __str__(self):
        return f"{self.provider} · {self.display_name}"


class Account(models.Model):
    """
    integrations.account
    """
    id = models.UUIDField(primary_key=True)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        db_column="integration_id",
        related_name="accounts",
    )
    provider_code = models.TextField()                 # text NOT NULL
    ext_account_id = models.TextField()                # text NOT NULL (внешний id в провайдере)
    display_name = models.TextField(null=True, blank=True)
    meta = models.JSONField(default=dict)              # jsonb NOT NULL DEFAULT '{}'

    class Meta:
        db_table = 'integrations"."account'
        managed = True
        constraints = [
            # UNIQUE (integration_id, ext_account_id)
            models.UniqueConstraint(
                fields=["integration", "ext_account_id"],
                name="account_integration_id_ext_account_id_key",
            ),
        ]

    def __str__(self):
        return self.display_name or self.ext_account_id


class AccountPortfolio(models.Model):
    """
    integrations.account_portfolio
    """
    id = models.UUIDField(primary_key=True)
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        db_column="account_id",
        related_name="portfolio_links",
    )
    portfolio = models.ForeignKey(
        "portfolio.Portfolio",
        on_delete=models.CASCADE,
        db_column="portfolio_id",
        related_name="integration_accounts",
    )
    # text[] поля
    instrument_types = ArrayField(models.TextField(), null=True, blank=True, default=list)
    venue_codes = ArrayField(models.TextField(), null=True, blank=True, default=list)
    symbols_include = ArrayField(models.TextField(), null=True, blank=True, default=list)
    symbols_exclude = ArrayField(models.TextField(), null=True, blank=True, default=list)
    is_primary = models.BooleanField(default=True)     # NOT NULL DEFAULT true

    class Meta:
        db_table = 'integrations"."account_portfolio'
        managed = True
        constraints = [
            # UNIQUE (account_id, portfolio_id)
            models.UniqueConstraint(
                fields=["account", "portfolio"],
                name="account_portfolio_account_id_portfolio_id_key",
            ),
        ]

    def __str__(self):
        return f"{self.account_id} ↔ {self.portfolio_id}"
