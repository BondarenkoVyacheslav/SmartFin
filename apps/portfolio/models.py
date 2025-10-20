from django.conf import settings
from django.db import models
from django.utils import timezone

class Portfolio(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolios")
    name = models.CharField(max_length=120)
    base_currency = models.CharField(max_length=10, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "name")]

class Position(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="positions")
    asset_id = models.IntegerField()  # связываешь со своим marketdata.Asset
    qty = models.DecimalField(max_digits=28, decimal_places=10, default=0)
    cost_basis = models.DecimalField(max_digits=28, decimal_places=10, default=0)  # средневзвешенная цена
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("portfolio", "asset_id")]

class Trade(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="trades")
    asset_id = models.IntegerField()
    qty = models.DecimalField(max_digits=28, decimal_places=10)      # покупка >0, продажа <0
    price = models.DecimalField(max_digits=28, decimal_places=10)    # цена сделки в валюте портфеля
    ts = models.DateTimeField(default=timezone.now)
    external_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)  # идемпотентность импорта

    class Meta:
        indexes = [models.Index(fields=["portfolio", "asset_id", "ts"])]
