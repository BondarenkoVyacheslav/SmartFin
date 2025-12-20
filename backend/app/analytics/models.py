from django.db import models

from app.assets.models import AssetType
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
                name="unique_daily_snapshot_per_portfolio",
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
                name="uniq_portfolio_asset_type_day",
            )
        ]
        ordering = ["-snapshot_date", "-id"]