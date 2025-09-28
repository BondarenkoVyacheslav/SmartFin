from datetime import datetime, timezone
from typing import List

import httpx
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Asset, AssetIdentifier, Currency, Price


MC_API = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"


class Command(BaseCommand):
    help = "Backfill crypto prices using CoinGecko market_chart (daily)"

    def add_arguments(self, parser):
        parser.add_argument("--symbols", required=True, help="Comma-separated asset symbols or CGK ids")
        parser.add_argument("--quote", default="USD")
        parser.add_argument("--days", default="30", help="Number of days of history")
        parser.add_argument("--source", default="COINGECKO")

    def handle(self, *args, **options):
        symbols = [s.strip() for s in options["symbols"].split(",") if s.strip()]
        quote = options["quote"].upper()
        days = options["days"]
        source = options["source"]

        try:
            quote_currency = Currency.objects.get(code=quote)
        except Currency.DoesNotExist:
            raise CommandError(f"Currency {quote} not found in DB")

        with httpx.Client(timeout=30.0) as client, transaction.atomic():
            for sym in symbols:
                cg_id = AssetIdentifier.objects.filter(id_type='CGK', asset__symbol__iexact=sym).values_list('id_value', flat=True).first() or sym
                url = MC_API.format(id=cg_id)
                r = client.get(url, params={"vs_currency": quote.lower(), "days": days})
                r.raise_for_status()
                data = r.json()
                prices = data.get("prices", [])
                try:
                    asset = Asset.objects.get(symbol__iexact=sym)
                except Asset.DoesNotExist:
                    continue
                for ts_ms, price_val in prices:
                    ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                    Price.objects.update_or_create(
                        asset=asset,
                        ts=ts,
                        source=source,
                        interval='day',
                        defaults={"price": price_val, "currency": quote_currency},
                    )
        self.stdout.write(self.style.SUCCESS("Backfilled crypto prices"))


