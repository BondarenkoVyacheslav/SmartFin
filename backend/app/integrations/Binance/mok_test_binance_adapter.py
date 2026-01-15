import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.app.integrations.Binance.adapter import BinanceAdapter


class FakeSpot:
    def __init__(self):
        self._now_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def account(self, **kwargs):
        return {
            "balances": [
                {"asset": "BTC", "free": "0.25", "locked": "0.05"},
                {"asset": "USDT", "free": "100.0", "locked": "0"},
            ]
        }

    def exchange_info(self, **kwargs):
        return {
            "symbols": [
                {"symbol": "BTCUSDT", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHUSDT", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "FOOBAR", "quoteAsset": "BAR", "status": "TRADING"},
            ]
        }

    def my_trades(self, **kwargs):
        symbol = kwargs.get("symbol")
        return [
            {
                "symbol": symbol,
                "id": 1,
                "price": "30000",
                "qty": "0.01",
                "commission": "0.00002",
                "commissionAsset": "BTC",
                "time": self._now_ms,
                "isBuyer": True,
            }
        ]

    def deposit_history(self, **kwargs):
        return {
            "depositList": [
                {
                    "coin": "USDT",
                    "amount": "50.0",
                    "insertTime": self._now_ms + 1000,
                    "transactionFee": "0",
                }
            ]
        }

    def withdraw_history(self, **kwargs):
        return {
            "withdrawList": [
                {
                    "coin": "USDT",
                    "amount": "10.0",
                    "applyTime": self._now_ms + 2000,
                    "transactionFee": "0.5",
                }
            ]
        }

    def convert_trade_history(self, **kwargs):
        return {
            "list": [
                {
                    "fromAsset": "USDT",
                    "toAsset": "BTC",
                    "fromAmount": "100.0",
                    "toAmount": "0.003",
                    "createTime": self._now_ms + 3000,
                }
            ]
        }


class FakeUMFutures:
    def __init__(self):
        self._now_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def account(self, **kwargs):
        return {
            "positions": [
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.02",
                    "entryPrice": "29500",
                    "markPrice": "30000",
                    "unRealizedProfit": "10",
                    "leverage": "10",
                    "positionSide": "LONG",
                }
            ]
        }

    def exchange_info(self, **kwargs):
        return {
            "symbols": [
                {"symbol": "BTCUSDT", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHUSDT", "quoteAsset": "USDT", "status": "TRADING"},
            ]
        }

    def user_trades(self, **kwargs):
        symbol = kwargs.get("symbol")
        return [
            {
                "symbol": symbol,
                "price": "29950",
                "qty": "0.01",
                "commission": "0.00001",
                "commissionAsset": "BTC",
                "time": self._now_ms + 1500,
                "side": "BUY",
            }
        ]


class FakeCMFutures:
    def __init__(self):
        self._now_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def account(self, **kwargs):
        return {
            "positions": [
                {
                    "symbol": "BTCUSD_PERP",
                    "positionAmt": "-1",
                    "entryPrice": "30000",
                    "markPrice": "29800",
                    "unrealizedProfit": "-20",
                    "leverage": "5",
                    "positionSide": "SHORT",
                }
            ]
        }

    def exchange_info(self, **kwargs):
        return {
            "symbols": [
                {"symbol": "BTCUSD_PERP", "quoteAsset": "USD", "status": "TRADING"},
            ]
        }

    def user_trades(self, **kwargs):
        symbol = kwargs.get("symbol")
        return [
            {
                "symbol": symbol,
                "price": "29900",
                "qty": "0.5",
                "commission": "0.0005",
                "commissionAsset": "BTC",
                "time": self._now_ms + 2500,
                "side": "SELL",
            }
        ]


class TestableBinanceAdapter(BinanceAdapter):
    def __init__(self, spot, um_futures, cm_futures, recv_window=5000):
        self._spot = spot
        self._um_futures = um_futures
        self._cm_futures = cm_futures
        self._recv_window = recv_window

    async def _call(self, func, /, *, signed: bool = False, **kwargs):
        if signed:
            kwargs.setdefault("recvWindow", self._recv_window)
        return func(**kwargs)


class BinanceAdapterMockTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TestableBinanceAdapter(FakeSpot(), FakeUMFutures(), FakeCMFutures())

    def test_fetch_balances(self):
        balances = asyncio.run(self.adapter.fetch_balances())
        self.assertEqual(len(balances), 2)
        btc = balances[0]
        self.assertEqual(btc.asset, "BTC")
        self.assertAlmostEqual(btc.total, 0.3, places=8)

    def test_fetch_positions(self):
        positions = asyncio.run(self.adapter.fetch_positions())
        self.assertEqual(len(positions), 2)
        symbols = {p.symbol for p in positions}
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("BTCUSD_PERP", symbols)

    def test_fetch_activities(self):
        activities = asyncio.run(self.adapter.fetch_activities(limit=50))
        kinds = {a.activity_type for a in activities}
        self.assertIn("spot_trade", kinds)
        self.assertIn("futures_trade", kinds)
        self.assertIn("deposit", kinds)
        self.assertIn("withdrawal", kinds)
        self.assertIn("conversion", kinds)
        timestamps = [a.timestamp for a in activities if a.timestamp]
        self.assertTrue(timestamps)

    def test_fetch_snapshot(self):
        snapshot = asyncio.run(self.adapter.fetch_snapshot(limit=50))
        self.assertTrue(snapshot.balances)
        self.assertTrue(snapshot.positions)
        self.assertTrue(snapshot.activities)


if __name__ == "__main__":
    unittest.main()
