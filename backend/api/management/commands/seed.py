from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction

from api import models


class Command(BaseCommand):
    help = "Seed baseline data into the database (idempotent)."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_currencies()
            self._seed_exchanges()
            user = self._seed_demo_user()
            portfolio = self._seed_portfolio(user)
            assets = self._seed_assets()
            self._seed_prices(assets)
            self._seed_fx()
            self._seed_transactions(portfolio, assets)
        self.stdout.write(self.style.SUCCESS("Seeding completed."))

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ensure_uuid(self, value: str | None = None) -> uuid.UUID:
        return uuid.uuid4() if value is None else uuid.UUID(value)

    def _seed_currencies(self) -> None:
        currencies = [
            ("USD", "US Dollar", 2, False),
            ("EUR", "Euro", 2, False),
            ("RUB", "Russian Ruble", 2, False),
            ("BTC", "Bitcoin", 8, True),
            ("ETH", "Ethereum", 8, True),
        ]
        for code, name, decimals, is_crypto in currencies:
            models.Currency.objects.update_or_create(
                code=code,
                defaults={
                    "id": uuid.uuid4(),
                    "name": name,
                    "decimals": decimals,
                    "is_crypto": is_crypto,
                    "created_at": self._now(),
                },
            )

    def _seed_exchanges(self) -> None:
        exchanges = [
            ("NYSE", "New York Stock Exchange", "US", "America/New_York"),
            ("NASDAQ", "NASDAQ", "US", "America/New_York"),
            ("MOEX", "Moscow Exchange", "RU", "Europe/Moscow"),
            ("BINANCE", "Binance", None, "UTC"),
        ]
        for code, name, country, tz in exchanges:
            models.Exchange.objects.update_or_create(
                code=code,
                defaults={
                    "id": uuid.uuid4(),
                    "name": name,
                    "country": country,
                    "timezone": tz,
                    "created_at": self._now(),
                },
            )

    def _seed_demo_user(self) -> models.AppUser:
        usd = models.Currency.objects.get(code="USD")
        user, _ = models.AppUser.objects.update_or_create(
            email="demo@finly.local",
            defaults={
                "id": uuid.uuid4(),
                "password_hash": None,
                "is_active": True,
                "base_currency": usd,
                "timezone": "UTC",
                "created_at": self._now(),
                "updated_at": self._now(),
            },
        )
        return user

    def _seed_portfolio(self, user: models.AppUser) -> models.Portfolio:
        usd = models.Currency.objects.get(code="USD")
        portfolio, _ = models.Portfolio.objects.update_or_create(
            user=user,
            name="Demo",
            defaults={
                "id": uuid.uuid4(),
                "base_currency": usd,
                "settings": {},
                "created_at": self._now(),
                "updated_at": self._now(),
            },
        )
        return portfolio

    def _seed_assets(self) -> dict[str, models.Asset]:
        usd = models.Currency.objects.get(code="USD")
        nyse = models.Exchange.objects.get(code="NYSE")
        nasdaq = models.Exchange.objects.get(code="NASDAQ")
        binance = models.Exchange.objects.get(code="BINANCE")

        asset_specs = [
            ("stock", "AAPL", "Apple Inc.", nasdaq, usd, "US0378331005"),
            ("stock", "MSFT", "Microsoft Corp.", nasdaq, usd, "US5949181045"),
            ("stock", "TSLA", "Tesla, Inc.", nasdaq, usd, "US88160R1014"),
            ("crypto", "BTC", "Bitcoin", binance, usd, None),
            ("cash", "USD", "US Dollar Cash", None, usd, None),
        ]

        created: dict[str, models.Asset] = {}
        for cls, symbol, name, exchange, currency, isin in asset_specs:
            asset, _ = models.Asset.objects.update_or_create(
                symbol=symbol,
                exchange=exchange,
                defaults={
                    "id": uuid.uuid4(),
                    "class_field": cls,
                    "name": name,
                    "trading_currency": currency,
                    "isin": isin,
                    "metadata": {},
                    "is_active": True,
                    "created_at": self._now(),
                },
            )
            created[symbol] = asset
        return created

    def _seed_prices(self, assets: dict[str, models.Asset]) -> None:
        usd = models.Currency.objects.get(code="USD")
        base_time = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
        history_days = 10
        price_map = {
            "AAPL": 190.0,
            "MSFT": 420.0,
            "TSLA": 240.0,
            "BTC": 60000.0,
        }
        for symbol, start_price in price_map.items():
            asset = assets[symbol]
            for i in range(history_days):
                ts = base_time - timedelta(days=history_days - i)
                price_value = start_price * (1 + (i - history_days / 2) * 0.002)
                models.Price.objects.update_or_create(
                    asset=asset,
                    ts=ts,
                    source="SEED",
                    interval="day",
                    defaults={
                        "id": uuid.uuid4(),
                        "price": round(price_value, 2),
                        "currency": usd,
                        "metadata": {},
                        "created_at": self._now(),
                    },
                )

    def _seed_fx(self) -> None:
        usd = models.Currency.objects.get(code="USD")
        eur = models.Currency.objects.get(code="EUR")
        rub = models.Currency.objects.get(code="RUB")
        base_time = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
        pairs = [
            (usd, eur, 0.92),
            (usd, rub, 95.0),
        ]
        for base, quote, rate in pairs:
            for i in range(10):
                ts = base_time - timedelta(days=10 - i)
                models.FxRate.objects.update_or_create(
                    base_currency=base,
                    quote_currency=quote,
                    ts=ts,
                    source="SEED",
                    defaults={
                        "id": uuid.uuid4(),
                        "rate": rate,
                    },
                )

    def _seed_transactions(self, portfolio: models.Portfolio, assets: dict[str, models.Asset]) -> None:
        usd = models.Currency.objects.get(code="USD")
        now = self._now()

        tx_specs = [
            # Cash deposit
            ("USD", "deposit", now - timedelta(days=15), 10000, None, 0),
            # Buy AAPL 20 @ 185
            ("AAPL", "buy", now - timedelta(days=9), 20, 185.00, 1.00),
            # Buy MSFT 10 @ 410
            ("MSFT", "buy", now - timedelta(days=8), 10, 410.00, 1.00),
            # Buy TSLA 10 @ 230
            ("TSLA", "buy", now - timedelta(days=7), 10, 230.00, 1.00),
            # Buy BTC 0.05 @ 58000
            ("BTC", "buy", now - timedelta(days=6), 0.05, 58000.00, 5.00),
            # Dividend AAPL
            ("AAPL", "dividend", now - timedelta(days=5), 12.4, None, 0.0),
            # Fee
            ("USD", "fee", now - timedelta(days=5), 10.0, None, 0.0),
        ]

        for symbol, tx_type, ts, qty, price, fee in tx_specs:
            asset = assets[symbol]
            models.Transaction.objects.update_or_create(
                portfolio=portfolio,
                asset=asset,
                tx_type=tx_type,
                tx_time=ts,
                quantity=qty,
                defaults={
                    "id": uuid.uuid4(),
                    "price": price,
                    "price_currency": usd if price is not None else None,
                    "fee": fee,
                    "notes": None,
                    "metadata": {},
                    "created_at": now,
                },
            )


