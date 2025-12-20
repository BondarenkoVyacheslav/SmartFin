from django.db import models


class AssetType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)


class Asset(models.Model):
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=50, unique=True)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    market_url = models.CharField(max_length=255, unique=True)
    currency = models.CharField(max_length=100)
