from django.db import models

from app.assets.models import Asset
from app.portfolio.models import Portfolio


# Create your models here.

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("buy", "Покупка"),
        ("sell", "Продажа"),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"

    def __str__(self):
        return f"{self.transaction_type.upper()} {self.asset.symbol or self.asset.name}"