from django.db import models

from app.assets.models import Asset, AssetType
from app.portfolio.models import Portfolio


class PortfolioDailySnapshot(models.Model):
    """
    Daily aggregated metrics for a portfolio to derive day P&L and capital history.
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="daily_snapshots",
    )
    snapshot_date = models.DateField()
    capital = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)
    margin = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "snapshot_date"],
                name="portfolio_day_snapshot",
            )
        ]
        ordering = ["-snapshot_date", "-id"]

    def __str__(self) -> str:
        return f"{self.portfolio_id} {self.snapshot_date}"



class PortfolioAssetDailySnapshot(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="asset_type_daily_snapshot",
    )
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.CASCADE,
        related_name="portfolio_daily_snapshots_by_type",
    )
    snapshot_date = models.DateField()
    snapshot = models.DecimalField(max_digits=20, decimal_places=8)
    margin = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset_type", "snapshot_date"],
                name="portfolio_asset_type_day_snapshot",
            )
        ]
        ordering = ["-snapshot_date", "-id"]


class PortfolioValuationDaily(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="valuation_daily",
    )
    snapshot_date = models.DateField()
    base_currency = models.CharField(max_length=10)
    value_base = models.DecimalField(max_digits=20, decimal_places=8)
    net_flow_base = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    pnl_base = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "snapshot_date"],
                name="portfolio_valuation_daily_unique",
            )
        ]
        ordering = ["-snapshot_date", "-id"]


class PortfolioPositionDaily(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="position_daily",
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    snapshot_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price_base = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    value_base = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset", "snapshot_date"],
                name="portfolio_position_daily_unique",
            )
        ]
        ordering = ["-snapshot_date", "-id"]
