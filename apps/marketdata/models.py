# apps/marketdata/models.py
import uuid
from datetime import date
from django.db import models
from django.db.models import Q, F

class Provider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.TextField(unique=True)                # UNIQUE (code)
    kind = models.TextField()
    sla = models.TextField(null=True, blank=True)
    cost = models.JSONField(default=dict, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'marketdata"."provider'             # создастся в схеме marketdata
        # в дампе есть UNIQUE (code) — уже учтён через unique=True
        # :contentReference[oaicite:1]{index=1}

    def __str__(self):
        return f'{self.code} ({self.kind})'


class SymbolMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # FK → marketdata.provider (ON DELETE CASCADE)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        db_column='provider_id',
        related_name='symbol_maps',
    )

    external_symbol = models.TextField()

    # FK по НЕ-PK полю: market.exchange.code  (ON DELETE SET NULL)
    exchange = models.ForeignKey(
        'market.Exchange',
        to_field='code',
        db_column='exchange_code',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='symbol_maps',
    )

    # FK → market.asset (NO ACTION в SQL ≈ PROTECT в Django)
    asset = models.ForeignKey(
        'market.Asset',
        db_column='asset_id',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='symbol_maps',
    )

    metadata = models.JSONField(default=dict)

    # Валидность соответствия (см. CHECK и UX/EX в дампе)
    valid_from = models.DateField(default=date(1970, 1, 1))
    valid_to   = models.DateField(default=date(9999, 12, 31))

    class Meta:
        db_table = 'marketdata"."symbol_map'
        constraints = [
            # CHECK (valid_from <= valid_to)
            models.CheckConstraint(
                check=Q(valid_from__lte=F('valid_to')),
                name='ck_symbol_map_valid',
            ),
            # UNIQUE (provider_id, external_symbol, exchange_code)
            models.UniqueConstraint(
                fields=['provider', 'external_symbol', 'exchange'],
                name='ux_symbol_map',
            ),
        ]
        indexes = [
            # ускоряет ingest: (provider_id, external_symbol)
            models.Index(
                fields=['provider', 'external_symbol'],
                name='ix_symbol_map_provider_symbol',
            ),
        ]
        # В дампе ещё есть EXCLUDE (по периодам дат) + расширение btree_gist — это можно
        # добавить отдельной SQL-миграцией при необходимости. :contentReference[oaicite:2]{index=2}

    def __str__(self):
        exch = self.exchange_id or '—'
        return f'{self.provider_id}:{self.external_symbol}@{exch}'
