from django.contrib.auth import get_user_model
from django.db import models

from app.assets.models import Asset

# Create your models here.
User = get_user_model()


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    portfolio_asset = models.ManyToManyField(Asset, through="PortfolioAsset", related_name="portfolio_assets")
    transactions = models.ManyToManyField(Asset, through="transaction.Transaction",
                                          related_name="portfolio_transactions")
    created_at = models.DateTimeField(auto_now_add=True)
    base_currency = models.CharField(max_length=10, default="USD")

    class Meta:
        db_table = '"portfolio"."portfolio"'


class PortfolioAsset(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    avg_buy_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    buy_currency = models.CharField(max_length=10, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"portfolio"."portfolioasset"'
