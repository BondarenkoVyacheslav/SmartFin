# apps/portfolio/models.py
from django.conf import settings
from django.db import models
from apps.core.models import TransactionTypeEnumField
from apps.market.models import Currency, Asset


class Portfolio(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="portfolios",
    )
    name = models.CharField(max_length=255)
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        db_column="base_currency_id",
        related_name="portfolios",
    )
    settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolio"."portfolio'
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="portfolio_user_id_name_key"
            ),
        ]


class Position(models.Model):
    id = models.UUIDField(primary_key=True)
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        db_column="portfolio_id",
        related_name="positions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        db_column="asset_id",
        related_name="portfolio_positions",
    )
    qty = models.DecimalField(max_digits=38, decimal_places=18, default=0)
    cost_basis = models.DecimalField(max_digits=38, decimal_places=10, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolio"."position'  # таблица названа в БД как "position"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset"], name="position_portfolio_id_asset_id_key"
            ),
        ]


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True)
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        db_column="portfolio_id",
        related_name="transactions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        db_column="asset_id",
        related_name="transactions",
    )
    tx_type = TransactionTypeEnumField(db_column="tx_type")  # core.transaction_type_enum
    tx_time = models.DateTimeField(db_column="tx_time")

    quantity = models.DecimalField(max_digits=38, decimal_places=18, default=0)
    price = models.DecimalField(max_digits=38, decimal_places=10, null=True, blank=True)
    price_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        db_column="price_currency_id",
        null=True,
        blank=True,
        related_name="priced_transactions",
    )
    fee = models.DecimalField(max_digits=38, decimal_places=10, default=0)

    notes = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    linked_tx = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        db_column="linked_tx_id",
        null=True,
        blank=True,
        related_name="linked_children",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portfolio"."transaction'
        managed = True
        indexes = [
            models.Index(fields=["asset", "-tx_time"], name="ix_portfolio_tx_asset_time"),
            models.Index(fields=["portfolio", "-tx_time"], name="ix_portfolio_tx_portfolio_time"),
            models.Index(fields=["tx_type"], name="ix_portfolio_tx_type"),
        ]
        constraints = [
            # (price IS NULL) == (price_currency_id IS NULL)
            models.CheckConstraint(
                name="transaction_check",
                check=(
                    (models.Q(price__isnull=True) & models.Q(price_currency__isnull=True))
                    | (models.Q(price__isnull=False) & models.Q(price_currency__isnull=False))
                ),
            ),
        ]
