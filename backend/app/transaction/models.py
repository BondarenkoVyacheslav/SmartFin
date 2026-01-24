from django.db import models

from app.assets.models import Asset
from app.portfolio.models import Portfolio


# Create your models here.

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("buy", "Покупка"),
        ("sell", "Продажа"),
        ("deposit", "Депозит"),
        ("withdrawal", "Вывод"),
        ("conversion", "Конвертация"),
        ("futures_buy", "Фьючерсы: покупка"),
        ("futures_sell", "Фьючерсы: продажа"),
    ]
    SOURCE_TYPES = [
        ("MANUAL", "Вручную"),
        ("INTEGRATION", "Интеграция"),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    price_currency = models.CharField(max_length=10, null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_TYPES,
        default="MANUAL",
    )
    integration_dedupe_key = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = '"transaction"."transaction"'
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "integration_dedupe_key"],
                name="tx_integration_dedupe_unique",
            )
        ]

    def __str__(self):
        return f"{self.transaction_type.upper()} {self.asset.symbol or self.asset.name}"
