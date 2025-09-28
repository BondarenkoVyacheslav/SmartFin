from datetime import date, datetime, timedelta, timezone
from typing import List

import httpx
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Currency, FxRate


RANGE_API = "https://api.frankfurter.app/{start}..{end}"


class Command(BaseCommand):
    help = "Backfill FX rates from Frankfurter over a date range (daily)"

    def add_arguments(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--quotes", required=True, help="Comma-separated quotes")
        parser.add_argument("--start", required=True, help="YYYY-MM-DD")
        parser.add_argument("--end", required=True, help="YYYY-MM-DD")
        parser.add_argument("--source", default="ECB")

    def handle(self, *args, **options):
        base = options["base"].upper()
        quotes: List[str] = [q.strip().upper() for q in options["quotes"].split(",") if q.strip()]
        start = options["start"]
        end = options["end"]
        source = options["source"]

        try:
            base_currency = Currency.objects.get(code=base)
        except Currency.DoesNotExist:
            raise CommandError(f"Currency {base} not found in DB")

        url = RANGE_API.format(start=start, end=end)
        params = {"from": base, "to": ",".join(quotes)}
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        series = data.get("rates", {})
        total = 0
        with transaction.atomic():
            for d, day_rates in series.items():
                ts = datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
                for q, rate in day_rates.items():
                    try:
                        quote_currency = Currency.objects.get(code=q)
                    except Currency.DoesNotExist:
                        continue
                    FxRate.objects.update_or_create(
                        base_currency=base_currency,
                        quote_currency=quote_currency,
                        ts=ts,
                        source=source,
                        defaults={"rate": rate},
                    )
                    total += 1
        self.stdout.write(self.style.SUCCESS(f"Backfilled {total} FX rate points for {base}"))


