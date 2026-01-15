from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.assets.models import Asset, AssetType
from app.marketdata.CoinGecko.cache_keys import CoinGeckoCacheKeys
from app.marketdata.CoinGecko.coingecko import CoinGeckoProvider
from app.marketdata.CoinGecko.dto.coins_list import CoinsList
from app.marketdata.CoinGecko.dto.simple_price import ListSimplePricesEntry
from app.marketdata.MOEX.cache_keys import MOEXCacheKeys
from app.marketdata.MOEX.dto.stock_shares_TQBR_securities import MOEXSharesTQBRSecurities
from app.marketdata.MOEX.moex import MOEXProvider
from app.marketdata.USA.cache_keys import USAStockCacheKeys
from app.marketdata.USA.dto.quote import USAStockQuote
from app.marketdata.USA.usa import USAStockProvider
from app.marketdata.provider import Quote, Candle


class MarketDataAPI:
    _asset_type_name_to_provider = {
        "Криптовалюты": "crypto",
        "Акции РФ": "stock-ru",
        "Акции США": "stock-us",
    }

    def __init__(self, *, redis_url: Optional[str] = None) -> None:
        self.usa_provider = USAStockProvider(redis_url=redis_url)
        self.moex_provider = MOEXProvider(redis_url=redis_url)
        self.coin_gecko_provider = CoinGeckoProvider(redis_url=redis_url)
        self._asset_type_id_to_provider: Optional[Dict[int, str]] = None

    @staticmethod
    def _normalize_symbols(symbols: Sequence[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for symbol in symbols:
            if not symbol:
                continue
            normalized = symbol.strip().upper()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("MarketDataAPI cannot run async code from a running event loop")

    def _load_asset_type_mapping(self) -> Dict[int, str]:
        if self._asset_type_id_to_provider is not None:
            return self._asset_type_id_to_provider

        names = list(self._asset_type_name_to_provider.keys())
        name_to_id = dict(
            AssetType.objects.filter(name__in=names).values_list("name", "id")
        )
        mapping: Dict[int, str] = {}
        for name, provider in self._asset_type_name_to_provider.items():
            asset_type_id = name_to_id.get(name)
            if asset_type_id is not None:
                mapping[asset_type_id] = provider

        self._asset_type_id_to_provider = mapping
        return mapping

    def _provider_for_asset(self, asset: Asset) -> Optional[str]:
        mapping = self._load_asset_type_mapping()
        provider = mapping.get(asset.asset_type_id)
        if provider is not None:
            return provider
        return self._asset_type_name_to_provider.get(asset.asset_type.name)

    def health(self) -> Dict[str, Any]:
        return {"status": "ok"}

    def get_quote_by_symbol(self, symbol: str) -> Optional[Quote]:
        quotes = self.get_quotes_by_symbols([symbol])
        return quotes[0] if quotes else None

    def get_quotes_by_symbols(self, symbols: Sequence[str]) -> List[Quote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        assets = list(
            Asset.objects.select_related("asset_type").filter(symbol__in=normalized)
        )
        asset_by_symbol = {asset.symbol.upper(): asset for asset in assets}

        provider_symbols: Dict[str, List[str]] = {}
        for symbol in normalized:
            asset = asset_by_symbol.get(symbol)
            if asset is None:
                continue
            provider = self._provider_for_asset(asset)
            if provider is None:
                continue
            provider_symbols.setdefault(provider, []).append(symbol)

        quotes_by_symbol: Dict[str, Quote] = {}
        for provider, provider_symbols_list in provider_symbols.items():
            if provider == "stock-us":
                quotes = self._run_async(self._get_usa_quotes(provider_symbols_list))
            elif provider == "stock-ru":
                quotes = self._run_async(self._get_moex_quotes(provider_symbols_list))
            elif provider == "crypto":
                quotes = self._run_async(self._get_crypto_quotes(provider_symbols_list))
            else:
                continue

            for quote in quotes:
                quotes_by_symbol[quote.symbol.upper()] = quote

        return [quotes_by_symbol[symbol] for symbol in normalized if symbol in quotes_by_symbol]

    def get_quotes(self, symbols: List[str], asset_class: str) -> List[Quote]:
        if asset_class == "stock-us":
            return self._run_async(self._get_usa_quotes(symbols))
        if asset_class == "stock-ru":
            return self._run_async(self._get_moex_quotes(symbols))
        if asset_class == "crypto":
            return self._run_async(self._get_crypto_quotes(symbols))
        return []

    def get_candles(
        self,
        symbol: str,
        interval: str,
        asset_class: str,
        since: Optional[date] = None,
        till: Optional[date] = None,
    ) -> List[Candle]:
        return []

    def get_fx_rates(self, pairs: List[str], source: Optional[str] = None) -> Dict[str, float]:
        return {}

    @staticmethod
    def _quote_from_usa_dto(dto: USAStockQuote) -> Quote:
        return Quote(
            symbol=dto.symbol,
            last=dto.last,
            bid=dto.bid,
            ask=dto.ask,
            ts=dto.ts,
        )

    async def _get_usa_quote_from_cache(self, symbol: str) -> Optional[Quote]:
        key = USAStockCacheKeys.quote(symbol)
        cached = await self.usa_provider.cache.get(key)
        dto = USAStockQuote.from_redis_value(cached)
        if dto is None:
            return None
        return self._quote_from_usa_dto(dto)

    async def _get_usa_quote(self, symbol: str) -> Optional[Quote]:
        cached = await self._get_usa_quote_from_cache(symbol)
        if cached is not None and cached.last is not None:
            return cached

        dto = await self.usa_provider.quote(symbol)
        if dto is None:
            return None
        return self._quote_from_usa_dto(dto)

    async def _get_usa_quotes(self, symbols: Sequence[str]) -> List[Quote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        keys = [USAStockCacheKeys.quote(symbol) for symbol in normalized]
        cached = await self.usa_provider.cache.get_many(keys)

        cached_quotes: Dict[str, USAStockQuote] = {}
        missing: List[str] = []

        for symbol in normalized:
            cache_key = USAStockCacheKeys.quote(symbol)
            dto = USAStockQuote.from_redis_value(cached.get(cache_key))
            if dto is not None and dto.last is not None:
                cached_quotes[symbol] = dto
            else:
                missing.append(symbol)

        fresh_quotes = await self.usa_provider.quotes(missing)
        merged: Dict[str, USAStockQuote] = {**cached_quotes, **{q.symbol: q for q in fresh_quotes}}
        return [self._quote_from_usa_dto(merged[s]) for s in normalized if s in merged]

    @staticmethod
    def _quote_from_moex_dto(dto: MOEXSharesTQBRSecurities, symbol: str) -> Optional[Quote]:
        if dto is None:
            return None
        for row in dto.marketdata:
            if row.secid.upper() != symbol:
                continue
            last = row.last
            if last is None:
                last = row.market_price or row.close_price or row.l_current_price
            ts = row.sys_time or datetime.now(timezone.utc)
            return Quote(
                symbol=symbol,
                last=last,
                bid=row.bid,
                ask=row.offer,
                ts=ts,
            )
        return None

    async def _get_moex_quote_from_cache(self, symbol: str) -> Optional[Quote]:
        key = MOEXCacheKeys.stock_shares_TQBR_securities(symbol)
        cached = await self.moex_provider.cache.get(key)
        dto = MOEXSharesTQBRSecurities.from_redis_value(cached)
        return self._quote_from_moex_dto(dto, symbol)

    async def _get_moex_quote(self, symbol: str) -> Optional[Quote]:
        cached = await self._get_moex_quote_from_cache(symbol)
        if cached is not None and cached.last is not None:
            return cached

        dto = await self.moex_provider.stock_shares_TQBR_securities(symbol)
        return self._quote_from_moex_dto(dto, symbol)

    async def _get_moex_quotes(self, symbols: Sequence[str]) -> List[Quote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        quotes: List[Quote] = []
        for symbol in normalized:
            quote = await self._get_moex_quote(symbol)
            if quote is not None:
                quotes.append(quote)
        return quotes

    async def _coingecko_coins_list_cached(
        self,
        include_platform: bool,
        *,
        cache_only: bool = False,
    ) -> Optional[CoinsList]:
        key = CoinGeckoCacheKeys.coins_list(include_platform)
        cached = await self.coin_gecko_provider.cache.get(key)
        dto = CoinsList.from_redis_value(cached)
        if dto is not None:
            return dto
        if cache_only:
            return None
        return await self.coin_gecko_provider.coins_list(include_platform=include_platform)

    async def _coingecko_simple_price_cached(
        self,
        ids: Sequence[str],
        vs_currencies: Sequence[str],
        *,
        include_market_cap: bool = False,
        include_24hr_vol: bool = False,
        include_24hr_change: bool = False,
        include_last_updated_at: bool = False,
        cache_only: bool = False,
    ) -> Optional[ListSimplePricesEntry]:
        ids_csv = CoinGeckoProvider.csv(ids)
        vs_csv = CoinGeckoProvider.csv(vs_currencies)
        key = CoinGeckoCacheKeys.simple_price(
            ids_sig=CoinGeckoProvider.sig(ids_csv),
            vs_sig=CoinGeckoProvider.sig(vs_csv),
            opts_sig=CoinGeckoProvider.sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )
        cached = await self.coin_gecko_provider.cache.get(key)
        dto = ListSimplePricesEntry.from_redis_value(cached)
        if dto is not None:
            return dto
        if cache_only:
            return None
        return await self.coin_gecko_provider.simple_price(
            ids=ids,
            vs_currencies=vs_currencies,
            include_market_cap=include_market_cap,
            include_24hr_vol=include_24hr_vol,
            include_24hr_change=include_24hr_change,
            include_last_updated_at=include_last_updated_at,
        )

    async def _get_crypto_quote_from_cache(self, symbol: str) -> Optional[Quote]:
        quotes = await self._get_crypto_quotes([symbol], cache_only=True)
        return quotes[0] if quotes else None

    async def _get_crypto_quote(self, symbol: str) -> Optional[Quote]:
        quotes = await self._get_crypto_quotes([symbol])
        return quotes[0] if quotes else None

    async def _get_crypto_quotes(self, symbols: Sequence[str], *, cache_only: bool = False) -> List[Quote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        coins_list = await self._coingecko_coins_list_cached(False, cache_only=cache_only)
        if coins_list is None:
            return []

        symbol_to_id: Dict[str, str] = {}
        for coin in coins_list.coins_list:
            sym = (coin.symbol or "").lower()
            if sym and sym not in symbol_to_id:
                symbol_to_id[sym] = coin.id

        requested: List[tuple[str, str]] = []
        ids: List[str] = []
        for symbol in normalized:
            coin_id = symbol_to_id.get(symbol.lower())
            if coin_id:
                requested.append((symbol, coin_id))
                ids.append(coin_id)

        if not ids:
            return []

        prices = await self._coingecko_simple_price_cached(
            ids=ids,
            vs_currencies=["usd"],
            include_last_updated_at=True,
            cache_only=cache_only,
        )
        if prices is None:
            return []

        price_map: Dict[str, Any] = {}
        for entry in prices.simple_prices:
            if entry.vs_currency == "usd":
                price_map[entry.coin_id] = entry

        quotes: List[Quote] = []
        for symbol, coin_id in requested:
            entry = price_map.get(coin_id)
            if entry is None or entry.price is None:
                continue
            ts = datetime.fromtimestamp(entry.last_updated_at, tz=timezone.utc) if entry.last_updated_at else datetime.now(timezone.utc)
            quotes.append(
                Quote(
                    symbol=symbol,
                    last=entry.price,
                    bid=None,
                    ask=None,
                    ts=ts,
                )
            )
        return quotes
