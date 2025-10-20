from django.db import models

class PortfolioSnapshot(models.Model):
    """Материализованные метрики по портфелю на момент времени (по UTC)."""
    portfolio_id = models.IntegerField(db_index=True)
    as_of = models.DateTimeField(db_index=True)      # когда считали
    total_value = models.DecimalField(max_digits=28, decimal_places=10)
    pnl_1d = models.DecimalField(max_digits=28, decimal_places=10)
    pnl_7d = models.DecimalField(max_digits=28, decimal_places=10)
    pnl_30d = models.DecimalField(max_digits=28, decimal_places=10)

    class Meta:
        unique_together = [("portfolio_id", "as_of")]
        indexes = [models.Index(fields=["portfolio_id", "-as_of"])]
