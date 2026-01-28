from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.marketdata.Alpaca.alpaca import AlpacaProvider
from app.marketdata.CoinGecko.coingecko import CoinGeckoProvider
from app.marketdata.MOEX.moex import MOEXProvider


@dataclass(frozen=True)
class AssetPriceRequest:
    asset_type: str
    symbol: str
    currency: Optional[str] = None


@dataclass
class AssetPriceResult:
    asset_type: str
    symbol: str
    price: Optional[float]
    currency: Optional[str]


class MarketDataRouter:
    """
    Routes price requests to CoinGecko, MOEX, or Alpaca by asset type.
    Returns only price + quote currency for each request.
    """

    DEFAULT_CRYPTO_VS = "usd"

    COINGECKO_TYPES = {"crypto"}
    ALPACA_STOCK_TYPES = {"stock_us"}
    ALPACA_INDEX_TYPES = {"index_us", "us_index"}
    MOEX_TYPE_TO_METHOD = {
        "stock_ru": "stock_shares_TQBR_securities",
        "etf_ru": "stock_shares_TQTF_securities",
        "bond": "stock_bonds_TQCB_securities",
        "bond_ru": "stock_bonds_TQOB_securities",
        "currency": "currency_selt_CETS_securities",
        "index": "stock_index_SNDX_securities",
        "metal": "currency_selt_CETS_securities",
    }

    ASSET_TYPE_ALIASES = {
        "crypto_currency": "crypto",
        "cryptocurrency": "crypto",
        "stockus": "stock_us",
        "us_stock": "stock_us",
        "indexusa": "index_us",
        "indexus": "index_us",
        "bonds": "bond",
        "bond_rf": "bond_ru",
        "currency_ru": "currency",
        "moex_index": "index",
    }

    PRICE_ATTRS = (
        "last",
        "LAST",
        "current_value",
        "CURRENTVALUE",
        "last_value",
        "LASTVALUE",
        "market_price",
        "MARKETPRICE",
        "market_price_today",
        "MARKETPRICETODAY",
        "market_price2",
        "MARKETPRICE2",
        "close_price",
        "CLOSEPRICE",
        "waprice",
        "WAPRICE",
        "open",
        "OPEN",
    )

    CURRENCY_ATTRS = (
        "currency_id",
        "CURRENCYID",
        "currencyid",
        "currency",
        "CURRENCY",
        "face_unit",
        "FACEUNIT",
        "faceunit",
        "unit",
        "UNIT",
    )

    def __init__(
        self,
        *,
        coin_gecko: Optional[CoinGeckoProvider] = None,
        moex: Optional[MOEXProvider] = None,
        alpaca: Optional[AlpacaProvider] = None,
    ) -> None:
        self.coin_gecko = coin_gecko or CoinGeckoProvider()
        self.moex = moex or MOEXProvider()
        self.alpaca = alpaca or AlpacaProvider()

    async def aclose(self) -> None:
        await asyncio.gather(
            self.coin_gecko.aclose(),
            self.alpaca.aclose(),
        )

    async def get_prices(
        self,
        requests: Sequence[AssetPriceRequest],
    ) -> List[AssetPriceResult]:
        if not requests:
            return []

        normalized: List[Tuple[int, AssetPriceRequest, str, str, Optional[str]]] = []
        results: List[AssetPriceResult] = []

        for idx, req in enumerate(requests):
            asset_type = self._normalize_asset_type(req.asset_type)
            symbol = self._normalize_symbol(req.symbol)
            quote_ccy = self._normalize_currency(req.currency)
            normalized.append((idx, req, asset_type, symbol, quote_ccy))
            results.append(
                AssetPriceResult(
                    asset_type=req.asset_type,
                    symbol=req.symbol,
                    price=None,
                    currency=None,
                )
            )

        cg_groups: Dict[str, Dict[str, List[int]]] = {}
        alpaca_stock: Dict[str, List[int]] = {}
        alpaca_index: Dict[str, List[int]] = {}
        moex_groups: Dict[str, Dict[str, List[int]]] = {}

        for idx, _req, asset_type, symbol, quote_ccy in normalized:
            if not asset_type or not symbol:
                continue

            if asset_type in self.COINGECKO_TYPES:
                vs = (quote_ccy or self.DEFAULT_CRYPTO_VS).lower()
                cg_groups.setdefault(vs, {}).setdefault(symbol, []).append(idx)
                continue

            if asset_type in self.ALPACA_STOCK_TYPES:
                alpaca_stock.setdefault(symbol, []).append(idx)
                continue

            if asset_type in self.ALPACA_INDEX_TYPES:
                alpaca_index.setdefault(symbol, []).append(idx)
                continue

            method = self.MOEX_TYPE_TO_METHOD.get(asset_type)
            if method:
                moex_groups.setdefault(method, {}).setdefault(symbol, []).append(idx)

        tasks = []
        if cg_groups:
            tasks.append(self._fill_coingecko(cg_groups, results))
        if alpaca_stock or alpaca_index:
            tasks.append(self._fill_alpaca(alpaca_stock, alpaca_index, results))
        if moex_groups:
            tasks.append(self._fill_moex(moex_groups, results))

        if tasks:
            await asyncio.gather(*tasks)

        return results

    async def get_price(self, request: AssetPriceRequest) -> AssetPriceResult:
        results = await self.get_prices([request])
        return results[0] if results else AssetPriceResult(
            asset_type=request.asset_type,
            symbol=request.symbol,
            price=None,
            currency=None,
        )

    @classmethod
    def _normalize_asset_type(cls, asset_type: Optional[str]) -> str:
        if not asset_type:
            return ""
        normalized = asset_type.strip().lower().replace(" ", "_")
        return cls.ASSET_TYPE_ALIASES.get(normalized, normalized)

    @staticmethod
    def _normalize_symbol(symbol: Optional[str]) -> str:
        return (symbol or "").strip().upper()

    @staticmethod
    def _normalize_currency(currency: Optional[str]) -> Optional[str]:
        if not currency:
            return None
        value = str(currency).strip()
        return value.upper() if value else None

    async def _fill_coingecko(
        self,
        groups: Dict[str, Dict[str, List[int]]],
        results: List[AssetPriceResult],
    ) -> None:
        for vs_currency, symbol_map in groups.items():
            symbols = list(symbol_map.keys())
            dto = await self.coin_gecko.simple_price_by_symbols(symbols, [vs_currency])

            price_map: Dict[str, float] = {}
            for entry in dto.simple_prices_by_symbols:
                symbol = self._normalize_symbol(entry.symbol)
                if entry.vs_currency.lower() != vs_currency.lower():
                    continue
                price_map[symbol] = entry.price

            for symbol, indexes in symbol_map.items():
                price = price_map.get(symbol)
                for idx in indexes:
                    results[idx].price = price
                    results[idx].currency = vs_currency.upper() if price is not None else None

    async def _fill_alpaca(
        self,
        stock_map: Dict[str, List[int]],
        index_map: Dict[str, List[int]],
        results: List[AssetPriceResult],
    ) -> None:
        tasks = []

        if stock_map:
            tasks.append(self.alpaca.quotes(list(stock_map.keys())))
        if index_map:
            tasks.append(self.alpaca.index_quotes(list(index_map.keys())))

        if not tasks:
            return

        responses = await asyncio.gather(*tasks)
        offset = 0

        if stock_map:
            quotes = responses[offset]
            offset += 1
            for quote in quotes:
                symbol = self._normalize_symbol(quote.symbol)
                for idx in stock_map.get(symbol, []):
                    results[idx].price = quote.last
                    results[idx].currency = quote.currency

        if index_map:
            quotes = responses[offset]
            for quote in quotes:
                symbol = self._normalize_symbol(quote.symbol)
                for idx in index_map.get(symbol, []):
                    results[idx].price = quote.last
                    results[idx].currency = quote.currency

    async def _fill_moex(
        self,
        groups: Dict[str, Dict[str, List[int]]],
        results: List[AssetPriceResult],
    ) -> None:
        tasks = []
        for method, symbol_map in groups.items():
            tasks.append(self._fetch_moex_group(method, symbol_map, results))

        if tasks:
            await asyncio.gather(*tasks)

    async def _fetch_moex_group(
        self,
        method: str,
        symbol_map: Dict[str, List[int]],
        results: List[AssetPriceResult],
    ) -> None:
        symbols = list(symbol_map.keys())
        if not symbols:
            return

        max_batch = 10 if method == "stock_index_SNDX_securities" else 50
        for batch in self._chunked(symbols, max_batch):
            response = await self._call_moex_method(method, batch)
            if response is None:
                continue
            prices, currencies = self._build_moex_maps(response)
            for symbol in batch:
                price = prices.get(symbol)
                currency = currencies.get(symbol)
                for idx in symbol_map.get(symbol, []):
                    results[idx].price = price
                    results[idx].currency = currency

    async def _call_moex_method(self, method: str, symbols: Sequence[str]):
        csv = ",".join(symbols)
        if method == "stock_index_SNDX_securities":
            return await self.moex.stock_index_SNDX_securities(securities=csv)
        if method == "stock_shares_TQBR_securities":
            return await self.moex.stock_shares_TQBR_securities(securities=csv)
        if method == "stock_shares_TQTF_securities":
            return await self.moex.stock_shares_TQTF_securities(securities=csv)
        if method == "stock_bonds_TQCB_securities":
            return await self.moex.stock_bonds_TQCB_securities(securities=csv)
        if method == "stock_bonds_TQOB_securities":
            return await self.moex.stock_bonds_TQOB_securities(securities=csv)
        if method == "currency_selt_CETS_securities":
            return await self.moex.currency_selt_CETS_securities(securities=csv)
        return None

    @classmethod
    def _build_moex_maps(cls, response) -> Tuple[Dict[str, float], Dict[str, str]]:
        prices: Dict[str, float] = {}
        currencies: Dict[str, str] = {}

        securities = getattr(response, "securities", None) or []
        marketdata = getattr(response, "marketdata", None) or []

        if not securities:
            boards = getattr(response, "boards", None) or []
            securities = boards

        for item in securities:
            symbol = cls._extract_symbol(item)
            if not symbol:
                continue
            currency = cls._extract_currency(item)
            if currency:
                currencies[symbol] = currency

        for item in marketdata:
            symbol = cls._extract_symbol(item)
            if not symbol:
                continue
            price = cls._extract_price(item)
            if price is not None:
                prices[symbol] = price

        return prices, currencies

    @classmethod
    def _extract_symbol(cls, item) -> Optional[str]:
        for attr in ("secid", "SECID", "symbol", "SYMBOL"):
            value = getattr(item, attr, None)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return cls._normalize_symbol(text)
        return None

    @classmethod
    def _extract_currency(cls, item) -> Optional[str]:
        for attr in cls.CURRENCY_ATTRS:
            value = getattr(item, attr, None)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text.upper()
        return None

    @classmethod
    def _extract_price(cls, item) -> Optional[float]:
        for attr in cls.PRICE_ATTRS:
            value = getattr(item, attr, None)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _chunked(items: Sequence[str], size: int) -> Iterable[List[str]]:
        if size <= 0:
            yield list(items)
            return
        for i in range(0, len(items), size):
            yield list(items[i:i + size])
