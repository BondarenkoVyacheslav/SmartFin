# apps/analytics/models.py
from django.db import models

class PortfolioSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, serialize=False)
    portfolio = models.ForeignKey(
        to='portfolio.Portfolio',
        db_column='portfolio_id',
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    # timestamptz в БД → DateTimeField в Django
    as_of = models.DateTimeField()
    total_value = models.DecimalField(max_digits=38, decimal_places=10)
    pnl_1d = models.DecimalField(max_digits=38, decimal_places=10)
    pnl_7d = models.DecimalField(max_digits=38, decimal_places=10)
    pnl_30d = models.DecimalField(max_digits=38, decimal_places=10)

    class Meta:
        db_table = 'analytics"."portfolio_snapshot'
        managed = True
        # В БД есть уникальный ключ (portfolio_id, as_of)
        constraints = [
            models.UniqueConstraint(
                fields=('portfolio', 'as_of'),
                name='portfolio_snapshot_portfolio_id_as_of_key',
            ),
        ]
        indexes = [
            models.Index(fields=['portfolio', '-as_of'], name='ix_an_port_snap_port_date'),
        ]

    def __str__(self):
        return f'Snapshot({self.portfolio_id} @ {self.as_of:%Y-%m-%d})'


class PositionValuationDaily(models.Model):
    id = models.UUIDField(primary_key=True, serialize=False)
    portfolio = models.ForeignKey(
        to='portfolio.Portfolio',
        db_column='portfolio_id',
        on_delete=models.CASCADE,
        related_name='valuations_daily',
    )
    asset = models.ForeignKey(
        to='market.Asset',
        db_column='asset_id',
        on_delete=models.PROTECT,
        related_name='valuations_daily',
    )
    # DATE в БД → DateField в Django
    as_of = models.DateField()

    qty = models.DecimalField(max_digits=38, decimal_places=18)
    price = models.DecimalField(max_digits=38, decimal_places=10)

    price_currency = models.ForeignKey(
        to='market.Currency',
        db_column='price_currency_id',
        on_delete=models.PROTECT,
        related_name='valuations_daily_prices',
    )
    fx_to_base = models.DecimalField(max_digits=38, decimal_places=10)

    value_base = models.DecimalField(max_digits=38, decimal_places=10)
    cost_basis_base = models.DecimalField(max_digits=38, decimal_places=10, null=True, blank=True)

    realized_pnl_base = models.DecimalField(max_digits=38, decimal_places=10, default=0)
    unrealized_pnl_base = models.DecimalField(max_digits=38, decimal_places=10, default=0)
    income_acc_base = models.DecimalField(max_digits=38, decimal_places=10, default=0)

    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = 'analytics"."position_valuation_daily'
        managed = True
        # Процедура вставляет UPSERT по (portfolio_id, asset_id, as_of) → делаем уникальный ключ
        constraints = [
            models.UniqueConstraint(
                fields=('portfolio', 'asset', 'as_of'),
                name='position_valuation_daily_portfolio_id_asset_id_as_of_key',
            ),
        ]
        indexes = [
            models.Index(fields=['portfolio', '-as_of'], name='ix_an_posval_port_date'),
            models.Index(fields=['asset', '-as_of'], name='ix_an_posval_asset_date'),
        ]

    def __str__(self):
        return f'Val({self.portfolio_id}, {self.asset_id} @ {self.as_of})'
