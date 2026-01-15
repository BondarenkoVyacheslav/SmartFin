from django.db import models


class AssetType(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)


class Asset(models.Model):
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=50)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    market_url = models.CharField(max_length=255, unique=True)
    currency = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["symbol", "asset_type"], name="asset_symbol_asset_type_unique"),
        ]
