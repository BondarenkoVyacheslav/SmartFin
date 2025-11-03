# apps/assets/models.py
from django.db import models
from apps.core.models import AssetClassEnumField, PriceIntervalEnumField
from django.db import models
from django.db.models import Q, F
from apps.core.models import PriceIntervalEnumField
from django.db.models import Case, When, Value


class Currency(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=255)
    decimals = models.IntegerField(default=2)
    is_crypto = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assets"."currency'
        managed = True


class Exchange(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=64, null=True, blank=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assets"."exchange'
        managed = True


class Asset(models.Model):
    id = models.UUIDField(primary_key=True)
    asset_class = AssetClassEnumField(db_column='class')  # core.asset_class_enum
    symbol = models.CharField(max_length=128)
    name = models.CharField(max_length=255)
    trading_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, db_column='trading_currency_id', null=True, blank=True,
        related_name='assets'
    )
    isin = models.CharField(max_length=32, null=True, blank=True)
    exchange = models.ForeignKey(
        Exchange, on_delete=models.PROTECT, db_column='exchange_id', null=True, blank=True, related_name='assets'
    )
    metadata = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assets"."asset'
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
        db_table = 'assets"."asset_identifier'
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
    provider = models.ForeignKey(
        'marketdata.Provider',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='provider_id',
        related_name='market_prices',  # было 'prices' → стало уникально
        related_query_name='price',
    )

    class Meta:
        db_table = 'assets"."price'
        managed = True
        indexes = [
            models.Index(fields=['asset', '-ts'], name='ix_market_price_asset_ts'),
            models.Index(fields=['source'], name='ix_market_price_source'),
            models.Index(fields=['provider'], name='ix_market_price_provider'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['asset', 'ts', 'source', 'interval'],
                                    name='ux_price_asset_ts_source_interval'),
        ]


class FxRate(models.Model):
    id = models.UUIDField(primary_key=True)
    base_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, db_column='base_currency_id',
                                      related_name='fx_base')
    quote_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, db_column='quote_currency_id',
                                       related_name='fx_quote')
    ts = models.DateTimeField()
    rate = models.DecimalField(max_digits=38, decimal_places=10)
    source = models.CharField(max_length=64)
    provider = models.ForeignKey(
        'marketdata.Provider',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='provider_id',
        related_name='fx_rates',  # отличное имя для курсов
        related_query_name='fx_rate',
    )

    class Meta:
        db_table = 'assets"."fx_rate'
        managed = True
        indexes = [
            models.Index(fields=['base_currency', 'quote_currency', '-ts'], name='ix_market_fx_pair_ts'),
            models.Index(fields=['provider'], name='ix_market_fx_provider'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['base_currency', 'quote_currency', 'ts', 'source'],
                                    name='ux_fx_pair_ts_source'),
        ]


# --- QUOTE ---------------------------------------------------------------
class Quote(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey('assets.Asset', on_delete=models.CASCADE,
                              db_column='asset_id', related_name='quotes')
    ts = models.DateTimeField()
    bid = models.DecimalField(max_digits=38, decimal_places=10, null=True, blank=True)
    ask = models.DecimalField(max_digits=38, decimal_places=10, null=True, blank=True)
    # в БД это GENERATED ALWAYS STORED → делаем только для чтения
    mid = models.GeneratedField(
        expression=Case(
            When(bid__isnull=False, ask__isnull=False, then=(F('bid') + F('ask')) / Value(2)),
            When(bid__isnull=False, then=F('bid')),
            When(ask__isnull=False, then=F('ask')),
            default=None,
            output_field=models.DecimalField(max_digits=38, decimal_places=10),
        ),
        output_field=models.DecimalField(max_digits=38, decimal_places=10),
        db_persist=True,
        null=True, blank=True,
    )
    currency = models.ForeignKey('assets.Currency', on_delete=models.PROTECT,
                                 db_column='currency_id', related_name='quotes')
    provider = models.ForeignKey('marketdata.Provider', on_delete=models.SET_NULL,
                                 db_column='provider_id', related_name='quotes',
                                 null=True, blank=True)
    depth = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assets"."quote'
        managed = True  # таблица уже есть в БД
        indexes = [
            models.Index(fields=['asset', '-ts'], name='ix_quote_asset_ts'),
            models.Index(fields=['provider'], name='ix_quote_provider'),
        ]
        constraints = [
            # CHECK (bid <= ask) с допущением NULL-ов
            models.CheckConstraint(
                check=Q(bid__isnull=True) | Q(ask__isnull=True) | Q(bid__lte=F('ask')),
                name='quote_bid_ask_check',
            ),
            # Уникальность по (asset, ts) когда provider IS NULL
            models.UniqueConstraint(
                fields=['asset', 'ts'],
                name='uq_quote_no_provider',
                condition=Q(provider__isnull=True),
            ),
            # Уникальность по (asset, ts, provider) когда provider IS NOT NULL
            models.UniqueConstraint(
                fields=['asset', 'ts', 'provider'],
                name='uq_quote_with_provider',
                condition=Q(provider__isnull=False),
            ),
        ]

    def __str__(self):
        return f'Quote({self.asset_id} @ {self.ts})'


CA_ACTION_TYPES = ('split', 'merge', 'symbol_change', 'delisting', 'spin_off')


# --- CORPORATE ACTION ----------------------------------------------------
class CorporateAction(models.Model):
    class ActionType(models.TextChoices):
        SPLIT = 'split', 'Split'
        MERGE = 'merge', 'Merge'
        SYMBOL_CHANGE = 'symbol_change', 'Symbol change'
        DELISTING = 'delisting', 'Delisting'
        SPIN_OFF = 'spin_off', 'Spin-off'

    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey('assets.Asset', on_delete=models.PROTECT,
                              db_column='asset_id', related_name='corporate_actions')
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    ex_date = models.DateField()
    ratio = models.DecimalField(max_digits=38, decimal_places=10, null=True, blank=True)
    payload = models.JSONField(default=dict)

    class Meta:
        db_table = 'assets"."corporate_action'
        managed = True
        indexes = [
            models.Index(fields=['asset', 'ex_date'], name='ix_ca_asset_exdate'),
        ]
        constraints = [
            # CHECK (action_type IN (...))
            models.CheckConstraint(
                check=Q(action_type__in=CA_ACTION_TYPES),
                name='corporate_action_action_type_check',
            ),
        ]

    def __str__(self):
        return f'{self.action_type}({self.asset_id} @ {self.ex_date})'


# --- ASSET TAG  (композитный PK в БД) -----------------------------------
class AssetTag(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey('assets.Asset', on_delete=models.CASCADE, db_column='asset_id', related_name='tags')
    tag_type = models.TextField()
    tag_value = models.TextField()

    class Meta:
        db_table = 'assets"."asset_tag'
        constraints = [
            models.UniqueConstraint(fields=['asset', 'tag_type', 'tag_value'], name='ux_asset_tag')
        ]


    def save(self, *args, **kwargs):
        raise NotImplementedError("AssetTag — только для чтения из-за композитного PK в БД.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("AssetTag — только для чтения из-за композитного PK в БД.")

    def __str__(self):
        return f'{self.asset_id}:{self.tag_type}={self.tag_value}'


# --- BAR (OHLCV) ---------------------------------------------------------
class Bar(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey('assets.Asset', on_delete=models.CASCADE,
                              db_column='asset_id', related_name='bars')
    ts = models.DateTimeField()
    interval = PriceIntervalEnumField(db_column='interval')  # core.price_interval_enum
    open = models.DecimalField(max_digits=38, decimal_places=10)
    high = models.DecimalField(max_digits=38, decimal_places=10)
    low = models.DecimalField(max_digits=38, decimal_places=10)
    close = models.DecimalField(max_digits=38, decimal_places=10)
    volume = models.DecimalField(max_digits=38, decimal_places=18, null=True, blank=True)
    trades_count = models.IntegerField(null=True, blank=True)
    currency = models.ForeignKey('assets.Currency', on_delete=models.PROTECT,
                                 db_column='currency_id', related_name='bars')
    provider = models.ForeignKey('marketdata.Provider', on_delete=models.SET_NULL,
                                 db_column='provider_id', related_name='bars',
                                 null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assets"."bar'
        managed = True
        constraints = [
            models.CheckConstraint(
                check=Q(low__lte=F('open')) & Q(low__lte=F('close')) &
                      Q(high__gte=F('open')) & Q(high__gte=F('close')) &
                      Q(low__lte=F('high')),
                name='bar_ohlc_check',
            ),
            # Уникальность как в БД — отдельные partial-индексы
            models.UniqueConstraint(
                fields=['asset', 'ts', 'interval'],
                name='uq_bar_no_provider',
                condition=Q(provider__isnull=True),
            ),
            models.UniqueConstraint(
                fields=['asset', 'ts', 'interval', 'provider'],
                name='uq_bar_with_provider',
                condition=Q(provider__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=['asset', '-ts'], name='ix_bar_asset_ts'),
            models.Index(fields=['provider'], name='ix_bar_provider'),
        ]

    def __str__(self):
        return f'Bar({self.asset_id} {self.interval}@{self.ts})'
