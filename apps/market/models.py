# apps/market/models.py
from django.db import models
from apps.core.models import AssetClassEnumField, PriceIntervalEnumField

class Currency(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=255)
    decimals = models.IntegerField(default=2)
    is_crypto = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'market"."currency'
        managed = True

class Exchange(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=64, null=True, blank=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'market"."exchange'
        managed = True

class Asset(models.Model):
    id = models.UUIDField(primary_key=True)
    asset_class = AssetClassEnumField(db_column='class')  # core.asset_class_enum
    symbol = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    trading_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, db_column='trading_currency_id', null=True, blank=True, related_name='assets'
    )
    isin = models.CharField(max_length=32, null=True, blank=True)
    exchange = models.ForeignKey(
        Exchange, on_delete=models.PROTECT, db_column='exchange_id', null=True, blank=True, related_name='assets'
    )
    metadata = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'market"."asset'
        managed = True
        constraints = [
            models.UniqueConstraint(fields=['symbol', 'exchange'], name='ux_market_asset_symbol_exchange'),
        ]

class AssetIdentifier(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, db_column='asset_id', related_name='identifiers')
    id_type = models.CharField(max_length=64)
    id_value = models.CharField(max_length=255)

    class Meta:
        db_table = 'market"."asset_identifier'
        managed = True
        constraints = [
            models.UniqueConstraint(fields=['asset', 'id_type'], name='ux_asset_identifier_asset_id_type'),
            models.UniqueConstraint(fields=['id_type', 'id_value'], name='ux_asset_identifier_type_value'),
        ]

class Price(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, db_column='asset_id', related_name='prices')
    ts = models.DateTimeField()
    price = models.DecimalField(max_digits=38, decimal_places=10)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, db_column='currency_id', related_name='prices')
    source = models.CharField(max_length=64)
    interval = PriceIntervalEnumField(db_column='interval', default='day')  # core.price_interval_enum
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'market"."price'
        managed = True
        indexes = [
            models.Index(fields=['asset', '-ts'], name='ix_market_price_asset_ts'),
            models.Index(fields=['source'], name='ix_market_price_source'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['asset', 'ts', 'source', 'interval'],
                                    name='ux_price_asset_ts_source_interval'),
        ]

class FxRate(models.Model):
    id = models.UUIDField(primary_key=True)
    base_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, db_column='base_currency_id', related_name='fx_base')
    quote_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, db_column='quote_currency_id', related_name='fx_quote')
    ts = models.DateTimeField()
    rate = models.DecimalField(max_digits=38, decimal_places=10)
    source = models.CharField(max_length=64)

    class Meta:
        db_table = 'market"."fx_rate'
        managed = True
        indexes = [
            models.Index(fields=['base_currency', 'quote_currency', '-ts'], name='ix_market_fx_pair_ts'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['base_currency', 'quote_currency', 'ts', 'source'],
                                    name='ux_fx_pair_ts_source'),
        ]
