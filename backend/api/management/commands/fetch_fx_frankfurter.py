import asyncio
from datetime import datetime, timezone
from typing import List

import httpx
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Currency, FxRate


API = "https://api.frankfurter.app/latest"


class Command(BaseCommand):
    help = "Fetch latest FX rates from Frankfurter (ECB) for base->quotes"

    def add_arguments(self, parser):
        parser.add_argument("--base", default="USD")
        parser.add_argument("--quotes", default="EUR,GBP,JPY,RUB")
        parser.add_argument("--source", default="ECB")

    def handle(self, *args, **options):
        base = options["base"].upper()
        quotes: List[str] = [q.strip().upper() for q in options["quotes"].split(",") if q.strip()]
        source = options["source"]

        asyncio.run(self._run(base, quotes, source))

    async def _run(self, base: str, quotes: List[str], source: str):
        params = {"from": base, "to": ",".join(quotes)}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(API, params=params)
            r.raise_for_status()
            data = r.json()

        date_str = data.get("date")
        ts = datetime.now(timezone.utc)
        rates = data.get("rates", {})
        if not rates:
            raise CommandError("No rates returned")

        try:
            base_currency = Currency.objects.get(code=base)
        except Currency.DoesNotExist:
            raise CommandError(f"Currency {base} not found in DB")

        with transaction.atomic():
            for q, rate in rates.items():
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
        self.stdout.write(self.style.SUCCESS(f"Imported {len(rates)} FX pairs for {base} on {date_str}"))


