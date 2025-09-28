import asyncio
from datetime import datetime, timezone
from typing import List

import httpx
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Asset, Currency, Price, AssetIdentifier


API = "https://api.coingecko.com/api/v3/simple/price"


class Command(BaseCommand):
    help = "Fetch latest crypto prices from CoinGecko for symbols -> quote currency"

    def add_arguments(self, parser):
        parser.add_argument("--symbols", default="bitcoin,ethereum")
        parser.add_argument("--quote", default="USD")
        parser.add_argument("--source", default="COINGECKO")

    def handle(self, *args, **options):
        symbols: List[str] = [s.strip().lower() for s in options["symbols"].split(",") if s.strip()]
        quote = options["quote"].upper()
        source = options["source"]

        asyncio.run(self._run(symbols, quote, source))

    async def _run(self, symbols: List[str], quote: str, source: str):
        # map symbols to CoinGecko ids via asset_identifier if provided as tickers
        cg_ids: List[str] = []
        for sym in symbols:
            # allow passing either direct coingecko id or asset symbol that has CGK alias
            cg = AssetIdentifier.objects.filter(id_type='CGK', asset__symbol__iexact=sym).values_list('id_value', flat=True).first()
            cg_ids.append(cg or sym)

        params = {"ids": ",".join(cg_ids), "vs_currencies": quote.lower()}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(API, params=params)
            r.raise_for_status()
            data = r.json()

        try:
            quote_currency = Currency.objects.get(code=quote)
        except Currency.DoesNotExist:
            raise CommandError(f"Currency {quote} not found in DB")

        ts = datetime.now(timezone.utc)
        inserted = 0
        with transaction.atomic():
            for idx, sym in enumerate(symbols):
                key = cg_ids[idx]
                obj = data.get(key)
                if not obj or quote.lower() not in obj:
                    continue
                price_val = obj[quote.lower()]
                try:
                    asset = Asset.objects.get(symbol__iexact=sym)
                except Asset.DoesNotExist:
                    continue
                Price.objects.update_or_create(
                    asset=asset,
                    ts=ts,
                    source=source,
                    interval='day',
                    defaults={"price": price_val, "currency": quote_currency},
                )
                inserted += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {inserted} crypto prices in {quote}"))


