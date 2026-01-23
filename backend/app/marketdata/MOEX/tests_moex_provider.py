import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_ROOT))

from app.marketdata.MOEX.moex import MOEXProvider
from app.marketdata.MOEX.dto.currency_selt_CETS_securities import (
    MOEXCurrencySeltCETSSecurities,
    parse_moex_currency_selt_cets_securities_response,
)


class _CaptureCache:
    def __init__(self) -> None:
        self.set_calls: List[Tuple[str, str, Optional[int]]] = []

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        self.set_calls.append((key, value, ttl))
        return True


class _CaptureMOEXProvider(MOEXProvider):
    def __init__(self, payload: Dict[str, Any], cache: _CaptureCache) -> None:
        super().__init__(cache=cache)
        self._payload = payload
        self.last_get: Optional[Tuple[str, Dict[str, Any] | None]] = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.last_get = (path, params)
        return self._payload


class _NoCacheMOEXProvider(MOEXProvider):
    async def currency_selt_CETS_securities(
        self, securities: str = None
    ) -> MOEXCurrencySeltCETSSecurities:
        params = {
            "iss.meta": "off",
            "iss.only": "securities,marketdata,dataversion",
            "securities": securities,
        }

        data = await self._get(
            "/iss/engines/currency/markets/selt/boards/CETS/securities.json", params
        )
        return parse_moex_currency_selt_cets_securities_response(data)


def _payload_for_securities(secids: List[str]) -> Dict[str, Any]:
    securities_data = []
    marketdata_data = []
    yields_data = []
    for secid in secids:
        securities_data.append([secid, "CETS", secid, 1, "2025-01-20"])
        marketdata_data.append([secid, "CETS", 1.23, 1.22, 1.24])
        yields_data.append([secid, "CETS"])

    return {
        "securities": {
            "columns": ["SECID", "BOARDID", "SHORTNAME", "LOTSIZE", "SETTLEDATE"],
            "data": securities_data,
        },
        "marketdata": {
            "columns": ["SECID", "BOARDID", "LAST", "BID", "OFFER"],
            "data": marketdata_data,
        },
        "dataversion": {
            "columns": ["data_version", "seqnum", "trade_date", "trade_session_date"],
            "data": [[1, 2, "2025-01-20", "2025-01-20"]],
        },
        "marketdata_yields": {
            "columns": ["SECID", "BOARDID"],
            "data": yields_data,
        },
    }


class MOEXCurrencySeltCETSSecuritiesTests(unittest.IsolatedAsyncioTestCase):
    async def test_currency_selt_cets_securities_params_cache_and_parse(self) -> None:
        secids = ["BYNRUBTODTOM", "BYNRUB_TMS", "SLVRUB_TOM", "GLDRUB_TOM"]
        securities_param = ",".join(secids)
        payload = _payload_for_securities(secids)
        cache = _CaptureCache()
        provider = _CaptureMOEXProvider(payload, cache)

        result = await provider.currency_selt_CETS_securities(securities_param)

        self.assertIsInstance(result, MOEXCurrencySeltCETSSecurities)
        self.assertIsNotNone(provider.last_get)
        path, params = provider.last_get or ("", None)
        self.assertEqual(
            path,
            "/iss/engines/currency/markets/selt/boards/CETS/securities.json",
        )
        self.assertEqual(
            params,
            {
                "iss.meta": "off",
                "iss.only": "securities,marketdata,dataversion",
                "securities": securities_param,
            },
        )

        secids_out = [row.SECID for row in result.securities]
        for secid in secids:
            self.assertIn(secid, secids_out)

        self.assertEqual(len(cache.set_calls), 1)
        cache_key, cache_value, cache_ttl = cache.set_calls[0]
        self.assertEqual(cache_key, provider.Keys.currency_selt_CETS_securities(securities_param))
        self.assertEqual(cache_value, result.to_redis_value())
        self.assertEqual(cache_ttl, provider.TTL_CURRENCY_SELT_CETS_SECURITIES)


class MOEXCurrencySeltCETSSecuritiesLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_currency_selt_cets_securities_print_last(self) -> None:
        if os.getenv("MOEX_LIVE") not in {"1", "true", "yes"}:
            self.skipTest("Set MOEX_LIVE=1 to run live MOEX price output")

        secids = ["BYNRUBTODTOM", "BYNRUB_TMS", "SLVRUB_TOM", "GLDRUB_TOM"]
        securities_param = ",".join(secids)
        provider = _NoCacheMOEXProvider(cache=_CaptureCache())

        result = await provider.currency_selt_CETS_securities(securities_param)

        last_by_secid = {row.SECID: row.LAST for row in result.marketdata}
        print("MOEX CETS last prices:")
        for secid in secids:
            print(f"  {secid}: {last_by_secid.get(secid)}")


if __name__ == "__main__":
    unittest.main()
