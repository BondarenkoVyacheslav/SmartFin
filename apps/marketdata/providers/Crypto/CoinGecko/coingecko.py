from typing import Any, Dict, Optional, Sequence
import time
import httpx
import os
from hashlib import md5
from enum import Enum

from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_history import CoinHistory, parse_coin_history
from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_tickers import CoinTickers, parse_coin_tickers
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_list import parse_coins_list, CoinsList
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_markets import CoinsMarket, parse_coins_markets
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_id import CoinDetail, parse_coin_detail
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives import parse_derivatives, Derivatives
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchange_detail import DerivativesExchangeDetails, \
    parse_derivatives_exchange_details
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchanges import DerivativesExchangesPage, \
    parse_derivatives_exchanges
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchanges_list import DerivativesExchangesList, \
    parse_derivatives_exchanges_list
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_rates import ExchangeRates, parse_exchange_rates
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_tickers import parse_exchange_tickers, ExchangeTickers
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_volume_chart import parse_exchange_volume_chart, \
    ExchangeVolumeChart
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges import Exchanges, parse_exchanges
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges_list import ExchangesList, parse_exchanges_list
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_detail import Exchange, \
    parse_exchange as parse_exchange_for_exchange_detail
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_defi import parse_global_defi_data, GlobalDefiData
from apps.marketdata.providers.Crypto.CoinGecko.dto.ping import parser_ping, Ping
from apps.marketdata.providers.Crypto.CoinGecko.dto.search import SearchResult, parse_search_result
from apps.marketdata.providers.Crypto.CoinGecko.dto.search_trending import SearchTrendingResult, parse_search_trending
from apps.marketdata.providers.Crypto.CoinGecko.dto.simpl_token_price import SimpleTokenPricesList, \
    parse_simple_token_prices
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import ListSimplePricesEntry, parse_list_simple_price
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_data import GlobalData, parse_global
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import SupportedVSCurrencies, \
    parse_supported_vs_currencies
from apps.marketdata.providers.provider import Provider
from apps.marketdata.services.redis_cache import RedisCacheService
from apps.marketdata.providers.Crypto.CoinGecko.cache_keys import CoinGeckoCacheKeys



class CoinGeckoProvider(Provider):
    """
    CoinGecko API (Demo) провайдер.
    - REST через httpx
    - Кладёт результаты в Redis (через RedisCacheService) с разумными TTL
    - Поддерживает demo key: x-cg-demo-api-key (header) или query (резервно)
    """

    Keys = CoinGeckoCacheKeys

    # ===== Базовый префикс ключей =====
    KP = Keys.KP

    # ===== TTL по типам данных (сек) =====
    TTL_SIMPLE_PRICE = 30
    TTL_TOKEN_PRICE = 30
    TTL_SUPPORTED_VS_CURRENCIES = 24 * 3600 * 10
    TTL_COINS_LIST = 24 * 3600 * 3
    TTL_COINS_MARKETS = 60
    TTL_COIN_DETAIL = 10 * 60
    TTL_COIN_TICKERS = 5 * 60
    TTL_COIN_HISTORY = 24 * 3600
    TTL_EXCHANGES = 3600
    TTL_EXCHANGES_LIST = 24 * 3600
    TTL_EXCHANGE_DETAIL = 3600
    TTL_EXCHANGE_TICKERS = 15 * 60
    TTL_EXCHANGE_VOLUME_CHART = 3600
    TTL_DERIVATIVES = 60
    TTL_DERIVATIVES_EXCHANGES = 3600
    TTL_DERIVATIVES_EXCHANGE_DETAIL = 3600
    TTL_DERIVATIVES_EXCHANGES_LIST = 24 * 3600
    TTL_EXCHANGE_RATES = 6 * 3600
    TTL_SEARCH = 5 * 60
    TTL_TRENDING = 5 * 60
    TTL_GLOBAL = 5 * 60
    TTL_GLOBAL_DEFI = 10 * 60
    TTL_PUBLIC_TREASURY = 24 * 3600

    def __init__(
            self,
            cache,
            *,
            api_key: str = os.getenv("COIN_GECKO_API_DEMO_KEY"),
            base_url: str = "https://api.coingecko.com/api/v3",
            timeout_s: int = 12,
            user_agent: str = "SmartFin/CoinGeckoProvider/1.0",
            pass_key_in_query: bool = False,  # альтернативная подача ключа через query
    ) -> None:
        super().__init__(cache)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.pass_key_in_query = pass_key_in_query
        self.http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent,
                     **({"x-cg-demo-api-key": api_key} if api_key and not pass_key_in_query else {})}
        )

    # ============ helpers ============

    @staticmethod
    def csv(items: Sequence[str]) -> str:
        return ",".join(sorted({i.strip().lower() for i in items if i}))

    @staticmethod
    def sig(*parts: str) -> str:
        """Короткая подпись (чтобы ключи не разрастались)"""
        raw = "|".join(parts)
        return md5(raw.encode("utf-8")).hexdigest()[:10]

    def _q(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query-параметры + (опционально) demo-key как query."""
        params = dict(params or {})
        if self.api_key and self.pass_key_in_query:
            params["x_cg_demo_api_key"] = self.api_key
        return params

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET с простым бэкоффом и обработкой 429."""
        backoff = [0.2, 0.5, 1.0, 2.0, 4.0]
        last_err = None
        for i, delay in enumerate(backoff):
            try:
                r = self.http.get(path, params=self._q(params))
                if r.status_code == 429:
                    # Если отдали Retry-After — уважим
                    ra = r.headers.get("Retry-After")
                    sleep = float(ra) if ra else delay
                    time.sleep(sleep)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                if i == len(backoff) - 1:
                    raise
                time.sleep(delay)
        raise last_err or RuntimeError("unreachable")

    # ============ Ключи кеша (читаемые и стабильные) ============

    def k_simple_price(self, ids_sig: str, vs_sig: str, opts_sig: str) -> str:
        return self.Keys.simple_price(ids_sig, vs_sig, opts_sig)

    def k_token_price(self, platform: str, addrs_sig: str, vs_sig: str, opts_sig: str) -> str:
        return self.Keys.token_price(platform, addrs_sig, vs_sig, opts_sig)

    def k_supported_vs_currencies(self) -> str:
        return self.Keys.supported_vs_currencies()

    def k_coins_list(self, include_platform: bool) -> str:
        return self.Keys.coins_list(include_platform)

    def k_coins_markets(
            self,
            vs: str,
            page: int,
            order: str,
            spark: bool,
            pcp: str,
            ids_sig: Optional[str],
            category: Optional[str],
    ) -> str:
        return self.Keys.coins_markets(
            vs=vs,
            page=page,
            order=order,
            spark=spark,
            pcp=pcp,
            ids_sig=ids_sig,
            category=category,
        )

    def k_coin_detail(self, coin_id: str) -> str:
        return self.Keys.coin_detail(coin_id)

    def k_coin_tickers(self, coin_id: str, page: int) -> str:
        return self.Keys.coin_tickers(coin_id, page)

    def k_coin_history(self, coin_id: str, date_ddmmyyyy: str, localization: bool) -> str:
        return self.Keys.coin_history(coin_id, date_ddmmyyyy, localization)

    def k_exchanges(self, page: int) -> str:
        return self.Keys.exchanges(page)

    def k_exchanges_list(self) -> str:
        return self.Keys.exchanges_list()

    def k_exchange_detail(self, ex_id: str) -> str:
        return self.Keys.exchange_detail(ex_id)

    def k_exchange_tickers(self, ex_id: str, page: int) -> str:
        return self.Keys.exchange_tickers(ex_id, page)

    def k_exchange_volume_chart(self, ex_id: str, days: int) -> str:
        return self.Keys.exchange_volume_chart(ex_id, days)

    def k_derivatives(self) -> str:
        return self.Keys.derivatives()

    def k_derivatives_exchanges(self, page: int) -> str:
        return self.Keys.derivatives_exchanges(page)

    def k_derivatives_exchange_detail(self, ex_id: str) -> str:
        return self.Keys.derivatives_exchange_detail(ex_id)

    def k_derivatives_exchanges_list(self) -> str:
        return self.Keys.derivatives_exchanges_list()

    def k_exchange_rates(self) -> str:
        return self.Keys.exchange_rates()

    def k_search(self, query_sig: str) -> str:
        return self.Keys.search(query_sig)

    def k_trending(self) -> str:
        return self.Keys.trending()

    def k_global(self) -> str:
        return self.Keys.global_data()

    def k_global_defi(self) -> str:
        return self.Keys.global_defi()

    # ============ Endpoints ============

    # Ping / Auth
    async def ping(self) -> Optional[Ping]:
        data = await self._get("/ping")
        ping = await parser_ping(data)
        return ping

    # Simple
    async def simple_price(
            self,
            ids: Sequence[str],
            vs_currencies: Sequence[str],
            include_market_cap: bool = False,
            include_24hr_vol: bool = False,
            include_24hr_change: bool = False,
            include_last_updated_at: bool = False,
    ) -> ListSimplePricesEntry:
        ids_csv = self.csv(ids)
        vs_csv = self.csv(vs_currencies)
        params = {
            "ids": ids_csv,
            "vs_currencies": vs_csv,
            "include_market_cap": str(include_market_cap).lower(),
            "include_24hr_vol": str(include_24hr_vol).lower(),
            "include_24hr_change": str(include_24hr_change).lower(),
            "include_last_updated_at": str(include_last_updated_at).lower(),
        }
        data = await self._get("/simple/price", params)

        list_simple_prices_entry: ListSimplePricesEntry = parse_list_simple_price(data)

        key = self.k_simple_price(
            ids_sig=self.sig(ids_csv),
            vs_sig=self.sig(vs_csv),
            opts_sig=self.sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )

        await self.cache.set(key, list_simple_prices_entry.to_redis_value(), ttl=self.TTL_SIMPLE_PRICE)
        return list_simple_prices_entry

    async def simple_token_price(
            self,
            asset_platform_id: str,
            contract_addresses: Sequence[str],
            vs_currencies: Sequence[str],
            include_market_cap: bool = False,
            include_24hr_vol: bool = False,
            include_24hr_change: bool = False,
            include_last_updated_at: bool = False,
    ) -> SimpleTokenPricesList:
        addrs_csv = self.csv(contract_addresses)
        vs_csv = self.csv(vs_currencies)
        params = {
            "contract_addresses": addrs_csv,
            "vs_currencies": vs_csv,
            "include_market_cap": str(include_market_cap).lower(),
            "include_24hr_vol": str(include_24hr_vol).lower(),
            "include_24hr_change": str(include_24hr_change).lower(),
            "include_last_updated_at": str(include_last_updated_at).lower(),
        }
        path = f"/simple/token_price/{asset_platform_id}"
        data = await self._get(path, params)
        simple_token_price_list: SimpleTokenPricesList = parse_simple_token_prices(data)
        key = self.k_token_price(
            platform=asset_platform_id,
            addrs_sig=self.sig(addrs_csv),
            vs_sig=self.sig(vs_csv),
            opts_sig=self.sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )
        await self.cache.set(key, simple_token_price_list.to_redis_value(), ttl=self.TTL_TOKEN_PRICE)
        return simple_token_price_list

    async def simple_supported_vs_currencies(self) -> SupportedVSCurrencies:
        data = await self._get("/simple/supported_vs_currencies")
        supported_vs_currencies: SupportedVSCurrencies = parse_supported_vs_currencies(data)
        await self.cache.set(self.k_supported_vs_currencies(), supported_vs_currencies.to_redis_value(),
                             ttl=self.TTL_SUPPORTED_VS_CURRENCIES)

        return supported_vs_currencies

    # Coins
    async def coins_list(self, include_platform: bool = False) -> CoinsList:
        params = {"include_platform": str(include_platform).lower()} if include_platform else None
        data = await self._get("/coins/list", params)
        coins_list: CoinsList = parse_coins_list(data)
        await self.cache.set(self.k_coins_list(include_platform), coins_list.to_redis_value(), ttl=self.TTL_COINS_LIST)
        return coins_list

    async def coins_markets(
            self,
            vs_currency: str,
            *,
            ids: Optional[Sequence[str]] = None,
            category: Optional[str] = None,
            order: str = "market_cap_desc",
            per_page: int = 250,
            page: int = 1,
            sparkline: bool = False,
            price_change_percentage: str = "1h,24h,7d",
            locale: Optional[str] = None,
    ) -> CoinsMarket:
        params: Dict[str, Any] = {
            "vs_currency": vs_currency.lower(),
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower(),
            "price_change_percentage": price_change_percentage,
        }
        if ids:
            params["ids"] = self.csv(ids)
        if category:
            params["category"] = category
        if locale:
            params["locale"] = locale

        data = await self._get("/coins/markets", params)
        key = self.k_coins_markets(
            vs=vs_currency, page=page, order=order, spark=sparkline,
            pcp=price_change_percentage, ids_sig=self.sig(params["ids"]) if "ids" in params else None,
            category=category
        )
        coins_market: CoinsMarket = parse_coins_markets(data, vs_currency)
        await self.cache.set(key, coins_market.to_redis_value(), ttl=self.TTL_COINS_MARKETS)
        return coins_market

    async def coin_detail(
            self,
            coin_id: str,
            *,
            localization: bool = False,
            tickers: bool = True,
            market_data: bool = True,
            community_data: bool = True,
            developer_data: bool = True,
            sparkline: bool = False,
    ) -> CoinDetail:
        params = {
            "localization": str(localization).lower(),
            "tickers": str(tickers).lower(),
            "market_data": str(market_data).lower(),
            "community_data": str(community_data).lower(),
            "developer_data": str(developer_data).lower(),
            "sparkline": str(sparkline).lower(),
        }
        data = await self._get(f"/coins/{coin_id}", params)
        coin_detail: CoinDetail = parse_coin_detail(data)
        await self.cache.set(self.k_coin_detail(coin_id), coin_detail.to_redis_value(), ttl=self.TTL_COIN_DETAIL)
        return coin_detail

    class OrderEnum(str, Enum):
        TRUST_SCORE_DESC = "trust_score_desc"
        TRUST_SCORE_ASC = "trust_score_asc"
        VOLUME_DESC = "volume_desc"
        VOLUME_ASC = "volume_asc"

    class DexPairFormat(str, Enum):
        CONTRACT_ADDRESS = "contract_address"
        SYMBOL = "symbol"

    async def coin_tickers(
            self,
            coin_id: str,
            *,
            page: int = 1,
            exchange_ids: Optional[str] = None,
            include_exchange_logo: bool = True,
            order: OrderEnum = OrderEnum.TRUST_SCORE_DESC,
            depth: bool = False
    ) -> CoinTickers:
        params: Dict[str, Any] = {
            "page": page,
            "include_exchange_logo": str(include_exchange_logo).lower(),
            "order": order, "depth": str(depth).lower()
        }
        if exchange_ids: params["exchange_ids"] = exchange_ids
        data = await self._get(f"/coins/{coin_id}/tickers", params)

        coin_tickers: CoinTickers = parse_coin_tickers(data)

        await self.cache.set(
            self.k_coin_tickers(coin_id, page),
            coin_tickers.to_redis_value(),
            ttl=self.TTL_COIN_TICKERS
        )
        return coin_tickers

    async def coin_history(self, coin_id: str, date_ddmmyyyy: str, *, localization: bool = False) -> CoinHistory:
        params = {"date": date_ddmmyyyy, "localization": str(localization).lower()}
        data = await self._get(f"/coins/{coin_id}/history", params)
        coin_history: CoinHistory = parse_coin_history(data)
        await self.cache.set(
            self.k_coin_history(coin_id, date_ddmmyyyy, localization),
            coin_history.to_redis_value(),
            ttl=self.TTL_COIN_HISTORY
        )
        return coin_history

    # Exchanges
    async def exchanges(self, *, per_page: int = 250, page: int = 1) -> Exchanges:
        params = {"per_page": per_page, "page": page}
        data = await self._get("/exchanges", params)
        exchanges: Exchanges = parse_exchanges(data)

        await self.cache.set(self.k_exchanges(page), exchanges.to_redis_value(), ttl=self.TTL_EXCHANGES)
        return exchanges

    async def exchanges_list(self) -> ExchangesList:
        data = await self._get("/exchanges/list")
        exchanges_list: ExchangesList = parse_exchanges_list(data)
        await self.cache.set(self.k_exchanges_list(), exchanges_list.to_redis_value(), ttl=self.TTL_EXCHANGES_LIST)
        return exchanges_list

    async def exchange_detail(self, ex_id: str) -> Exchange:
        data = await self._get(f"/exchanges/{ex_id}")
        exchange: Exchange = parse_exchange_for_exchange_detail(data)
        await self.cache.set(self.k_exchange_detail(ex_id), exchange.to_redis_value(), ttl=self.TTL_EXCHANGE_DETAIL)
        return exchange

    class ExchangeTickersOrderEnum(str, Enum):
        MARKET_CAP_ASC = "market_cap_asc"
        MARKET_CAP_DESC = "market_cap_desc"
        TRUST_SCORE_DESC = "trust_score_desc"
        TRUST_SCORE_ASC = "trust_score_asc"
        VOLUME_DESC = "volume_desc"
        BASE_TARGET = "base_target"

    async def exchange_tickers(
            self, ex_id: str,
            *,
            page: int = 1,
            coin_ids: Optional[str] = None,
            depth: bool = False,
            order: ExchangeTickersOrderEnum = ExchangeTickersOrderEnum.TRUST_SCORE_DESC
    ) -> ExchangeTickers:
        params: Dict[str, Any] = {"page": page, "depth": str(depth).lower(), "order": order}
        if coin_ids: params["coin_ids"] = coin_ids
        data = await self._get(f"/exchanges/{ex_id}/tickers", params)
        ex_tickers: ExchangeTickers = parse_exchange_tickers(ex_id, data)
        await self.cache.set(self.k_exchange_tickers(ex_id, page), ex_tickers.to_redis_value(), ttl=self.TTL_EXCHANGE_TICKERS)
        return ex_tickers

    async def exchange_volume_chart(self, ex_id: str, days: int = 1) -> ExchangeVolumeChart:
        data = await self._get(f"/exchanges/{ex_id}/volume_chart", {"days": days})
        ex_volume_chart: ExchangeVolumeChart = parse_exchange_volume_chart(ex_id, days, data)
        await self.cache.set(
            self.k_exchange_volume_chart(ex_id, days),
            ex_volume_chart.to_redis_value(),
            ttl=self.TTL_EXCHANGE_VOLUME_CHART
        )
        return ex_volume_chart

    # Derivatives
    async def derivatives(self) -> Derivatives:
        data = await self._get("/derivatives")
        derivatives: Derivatives = parse_derivatives(data)
        await self.cache.set(self.k_derivatives(), derivatives.to_redis_value(), ttl=self.TTL_DERIVATIVES)
        return derivatives

    async def derivatives_exchanges(self, *, per_page: int = 250, page: int = 1) -> DerivativesExchangesPage:
        data = await self._get("/derivatives/exchanges", {"per_page": per_page, "page": page})
        derivatives_exchanges_page: DerivativesExchangesPage = parse_derivatives_exchanges(data, page=page)
        await self.cache.set(
            self.k_derivatives_exchanges(page),
            derivatives_exchanges_page.to_redis_value(),
            ttl=self.TTL_DERIVATIVES_EXCHANGES
        )
        return derivatives_exchanges_page

    async def derivatives_exchange_detail(self, ex_id: str) -> DerivativesExchangeDetails:
        data = await self._get(f"/derivatives/exchanges/{ex_id}")
        derivatives_exchange_details: DerivativesExchangeDetails = parse_derivatives_exchange_details(data)
        await self.cache.set(
            self.k_derivatives_exchange_detail(ex_id),
            derivatives_exchange_details.to_redis_value(),
            ttl=self.TTL_DERIVATIVES_EXCHANGE_DETAIL
        )
        return derivatives_exchange_details

    async def derivatives_exchanges_list(self) -> DerivativesExchangesList:
        data = await self._get("/derivatives/exchanges/list")
        derivatives_exchanges_list: DerivativesExchangesList = parse_derivatives_exchanges_list(data)
        await self.cache.set(
            self.k_derivatives_exchanges_list(),
            derivatives_exchanges_list.to_redis_value(),
            ttl=self.TTL_DERIVATIVES_EXCHANGES_LIST
        )
        return derivatives_exchanges_list

    # Exchange Rates
    async def exchange_rates(self) -> ExchangeRates:
        data = await self._get("/exchange_rates")
        exchange_rates: ExchangeRates = parse_exchange_rates(data)
        await self.cache.set(self.k_exchange_rates(), exchange_rates.to_redis_value(), ttl=self.TTL_EXCHANGE_RATES)
        return exchange_rates

    # Search & Trending
    async def search(self, query: str) -> SearchResult:
        data = await self._get("/search", {"query": query})
        search_result: SearchResult = parse_search_result(data)
        await self.cache.set(
            self.k_search(self.sig(query.strip().lower())),
            search_result.to_redis_value(),
            ttl=self.TTL_SEARCH
        )
        return search_result

    async def search_trending(self) -> SearchTrendingResult:
        data = await self._get("/search/trending")
        search_trending_result: SearchTrendingResult = parse_search_trending(data)
        await self.cache.set(self.k_trending(), search_trending_result.to_redis_value(), ttl=self.TTL_TRENDING)
        return search_trending_result

    # Global
    async def global_data(self) -> GlobalData:
        data = await self._get("/global")
        global_data: GlobalData = parse_global(data)
        await self.cache.set(self.k_global(), global_data.to_redis_value(), ttl=self.TTL_GLOBAL)
        return global_data

    async def global_defi(self) -> GlobalDefiData:
        data = await self._get("/global/decentralized_finance_defi")
        global_defi_data: GlobalDefiData = parse_global_defi_data(data)
        await self.cache.set(self.k_global_defi(), global_defi_data.to_redis_value(), ttl=self.TTL_GLOBAL_DEFI)
        return global_defi_data
