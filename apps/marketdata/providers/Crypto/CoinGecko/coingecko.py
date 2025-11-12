from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
import time
import httpx
import os
from hashlib import md5
from enum import Enum

from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_list import Coin, parse_coins_list, CoinsList
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_markets import CoinsMarket, parse_coins_markets
from apps.marketdata.providers.Crypto.CoinGecko.dto.coinst_id import CoinDetail, parse_coin_detail
from apps.marketdata.providers.Crypto.CoinGecko.dto.ping import parser_ping, Ping
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import parse_simple_price, SimplePriceEntry
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import SupportedVSCurrencies, \
    parse_supported_vs_currencies
from apps.marketdata.providers.provider import Provider
from apps.marketdata.services.redis_cache import RedisCacheService


class CoinGeckoProvider(Provider):
    """
    CoinGecko API (Demo) провайдер.
    - REST через httpx
    - Кладёт результаты в Redis (через RedisCacheService) с разумными TTL
    - Поддерживает demo key: x-cg-demo-api-key (header) или query (резервно)
    """

    # ===== Базовый префикс ключей =====
    KP = "v1:md:crypto:coingecko"

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
            cache: RedisCacheService,
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
    def _csv(items: Sequence[str]) -> str:
        return ",".join(sorted({i.strip().lower() for i in items if i}))

    @staticmethod
    def _sig(*parts: str) -> str:
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
        return f"{self.KP}:dto:simple:price:{ids_sig}:{vs_sig}:{opts_sig}"

    def k_token_price(self, platform: str, addrs_sig: str, vs_sig: str, opts_sig: str) -> str:
        return f"{self.KP}:simple:token_price:{platform.lower()}:{addrs_sig}:{vs_sig}:{opts_sig}"

    def k_supported_vs(self) -> str:
        return f"{self.KP}:simple:supported_vs"

    def k_coins_list(self, include_platform: bool) -> str:
        return f"{self.KP}:coins:list:{'with_platform' if include_platform else 'plain'}"

    def k_coins_markets(self, vs: str, page: int, order: str, spark: bool, pcp: str, ids_sig: Optional[str],
                        category: Optional[str]) -> str:
        base = f"{self.KP}:coins:markets:{vs}:{page}:{order}:{'spark' if spark else 'nospark'}:{pcp}"
        if category:
            base += f":cat:{category.lower()}"
        if ids_sig:
            base += f":ids:{ids_sig}"
        return base

    def k_coin_detail(self, coin_id: str) -> str:
        return f"{self.KP}:coins:{coin_id.lower()}:detail"

    def k_coin_tickers(self, coin_id: str, page: int) -> str:
        return f"{self.KP}:coins:{coin_id.lower()}:tickers:{page}"

    def k_coin_history(self, coin_id: str, date_ddmmyyyy: str, localization: bool) -> str:
        return f"{self.KP}:coins:{coin_id.lower()}:history:{date_ddmmyyyy}:{'loc' if localization else 'nloc'}"

    def k_exchanges(self, page: int) -> str:
        return f"{self.KP}:exchanges:page:{page}"

    def k_exchanges_list(self) -> str:
        return f"{self.KP}:exchanges:list"

    def k_exchange_detail(self, ex_id: str) -> str:
        return f"{self.KP}:exchanges:{ex_id.lower()}:detail"

    def k_exchange_tickers(self, ex_id: str, page: int) -> str:
        return f"{self.KP}:exchanges:{ex_id.lower()}:tickers:{page}"

    def k_exchange_volume_chart(self, ex_id: str, days: int) -> str:
        return f"{self.KP}:exchanges:{ex_id.lower()}:volume_chart:{days}d"

    def k_derivatives(self) -> str:
        return f"{self.KP}:derivatives"

    def k_derivatives_exchanges(self, page: int) -> str:
        return f"{self.KP}:derivatives:exchanges:{page}"

    def k_derivatives_exchange_detail(self, ex_id: str) -> str:
        return f"{self.KP}:derivatives:exchanges:{ex_id.lower()}:detail"

    def k_derivatives_exchanges_list(self) -> str:
        return f"{self.KP}:derivatives:exchanges:list"

    def k_exchange_rates(self) -> str:
        return f"{self.KP}:exchange_rates"

    def k_search(self, query_sig: str) -> str:
        return f"{self.KP}:search:{query_sig}"

    def k_trending(self) -> str:
        return f"{self.KP}:search:trending"

    def k_global(self) -> str:
        return f"{self.KP}:global"

    def k_global_defi(self) -> str:
        return f"{self.KP}:global:defi"

    def k_public_treasury(self, entity: str, coin_id: str) -> str:
        return f"{self.KP}:{entity.lower()}:public_treasury:{coin_id.lower()}"

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
    ) -> List[SimplePriceEntry]:
        ids_csv = self._csv(ids)
        vs_csv = self._csv(vs_currencies)
        params = {
            "ids": ids_csv,
            "vs_currencies": vs_csv,
            "include_market_cap": str(include_market_cap).lower(),
            "include_24hr_vol": str(include_24hr_vol).lower(),
            "include_24hr_change": str(include_24hr_change).lower(),
            "include_last_updated_at": str(include_last_updated_at).lower(),
        }
        data = await self._get("/simple/price", params)

        rows = await parse_simple_price(data)
        payload = [r.__dict__ for r in rows]

        key = self.k_simple_price(
            ids_sig=self._sig(ids_csv),
            vs_sig=self._sig(vs_csv),
            opts_sig=self._sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )

        await self.cache.set(key, payload, ttl=self.TTL_SIMPLE_PRICE)
        return rows

    async def simple_token_price(
            self,
            asset_platform_id: str,
            contract_addresses: Sequence[str],
            vs_currencies: Sequence[str],
            include_market_cap: bool = False,
            include_24hr_vol: bool = False,
            include_24hr_change: bool = False,
            include_last_updated_at: bool = False,
    ) -> Dict[str, Any]:
        addrs_csv = self._csv(contract_addresses)
        vs_csv = self._csv(vs_currencies)
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
        key = self.k_token_price(
            platform=asset_platform_id,
            addrs_sig=self._sig(addrs_csv),
            vs_sig=self._sig(vs_csv),
            opts_sig=self._sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )
        await self.cache.set(key, data, ttl=self.TTL_TOKEN_PRICE)
        return data

    async def simple_supported_vs_currencies(self) -> SupportedVSCurrencies:
        data = await self._get("/simple/supported_vs_currencies")
        supported_vs_currencies: SupportedVSCurrencies = parse_supported_vs_currencies(data)
        await self.cache.set(self.k_supported_vs(), supported_vs_currencies.to_redis_value(),
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
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "vs_currency": vs_currency.lower(),
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower(),
            "price_change_percentage": price_change_percentage,
        }
        if ids:
            params["ids"] = self._csv(ids)
        if category:
            params["category"] = category
        if locale:
            params["locale"] = locale

        data = await self._get("/coins/markets", params)
        key = self.k_coins_markets(
            vs=vs_currency, page=page, order=order, spark=sparkline,
            pcp=price_change_percentage, ids_sig=self._sig(params["ids"]) if "ids" in params else None,
            category=category
        )
        coins_market: CoinsMarket = parse_coins_markets(data, vs_currency)
        await self.cache.set(key, CoinsMarket.to_redis_value(), ttl=self.TTL_COINS_MARKETS)
        return data

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

    async def coin_tickers(self, coin_id: str, *, page: int = 1, exchange_ids: Optional[str] = None,
                           include_exchange_logo: bool = True, order: OrderEnum = OrderEnum.TRUST_SCORE_DESC, depth: bool = False) -> \
    Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "include_exchange_logo": str(include_exchange_logo).lower(),
                                  "order": order, "depth": str(depth).lower()}
        if exchange_ids:
            params["exchange_ids"] = exchange_ids
        data = await self._get(f"/coins/{coin_id}/tickers", params)
        await self.cache.set(self.k_coin_tickers(coin_id, page), data, ttl=self.TTL_COIN_TICKERS)
        return data

    async def coin_history(self, coin_id: str, date_ddmmyyyy: str, *, localization: bool = False) -> Dict[str, Any]:
        params = {"date": date_ddmmyyyy, "localization": str(localization).lower()}
        data = await self._get(f"/coins/{coin_id}/history", params)
        await self.cache.set(self.k_coin_history(coin_id, date_ddmmyyyy, localization), data, ttl=self.TTL_COIN_HISTORY)
        return data

    # Exchanges
    async def exchanges(self, *, per_page: int = 250, page: int = 1) -> List[Dict[str, Any]]:
        params = {"per_page": per_page, "page": page}
        data = await self._get("/exchanges", params)
        await self.cache.set(self.k_exchanges(page), data, ttl=self.TTL_EXCHANGES)
        return data

    async def exchanges_list(self) -> List[Dict[str, Any]]:
        data = await self._get("/exchanges/list")
        await self.cache.set(self.k_exchanges_list(), data, ttl=self.TTL_EXCHANGES_LIST)
        return data

    async def exchange_detail(self, ex_id: str) -> Dict[str, Any]:
        data = await self._get(f"/exchanges/{ex_id}")
        await self.cache.set(self.k_exchange_detail(ex_id), data, ttl=self.TTL_EXCHANGE_DETAIL)
        return data

    async def exchange_tickers(self, ex_id: str, *, page: int = 1, coin_ids: Optional[str] = None, depth: bool = False,
                               order: str = "trust_score_desc") -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "depth": str(depth).lower(), "order": order}
        if coin_ids:
            params["coin_ids"] = coin_ids
        data = await self._get(f"/exchanges/{ex_id}/tickers", params)
        await self.cache.set(self.k_exchange_tickers(ex_id, page), data, ttl=self.TTL_EXCHANGE_TICKERS)
        return data

    async def exchange_volume_chart(self, ex_id: str, days: int = 1) -> List[Tuple[int, float]]:
        data = await self._get(f"/exchanges/{ex_id}/volume_chart", {"days": days})
        await self.cache.set(self.k_exchange_volume_chart(ex_id, days), data, ttl=self.TTL_EXCHANGE_VOLUME_CHART)
        return data

    # Derivatives
    async def derivatives(self) -> List[Dict[str, Any]]:
        data = await self._get("/derivatives")
        await self.cache.set(self.k_derivatives(), data, ttl=self.TTL_DERIVATIVES)
        return data

    async def derivatives_exchanges(self, *, per_page: int = 250, page: int = 1) -> List[Dict[str, Any]]:
        data = await self._get("/derivatives/exchanges", {"per_page": per_page, "page": page})
        await self.cache.set(self.k_derivatives_exchanges(page), data, ttl=self.TTL_DERIVATIVES_EXCHANGES)
        return data

    async def derivatives_exchange_detail(self, ex_id: str) -> Dict[str, Any]:
        data = await self._get(f"/derivatives/exchanges/{ex_id}")
        await self.cache.set(self.k_derivatives_exchange_detail(ex_id), data, ttl=self.TTL_DERIVATIVES_EXCHANGE_DETAIL)
        return data

    async def derivatives_exchanges_list(self) -> List[Dict[str, Any]]:
        data = await self._get("/derivatives/exchanges/list")
        await self.cache.set(self.k_derivatives_exchanges_list(), data, ttl=self.TTL_DERIVATIVES_EXCHANGES_LIST)
        return data

    # Exchange Rates
    async def exchange_rates(self) -> Dict[str, Any]:
        data = await self._get("/exchange_rates")
        await self.cache.set(self.k_exchange_rates(), data, ttl=self.TTL_EXCHANGE_RATES)
        return data

    # Search & Trending
    async def search(self, query: str) -> Dict[str, Any]:
        data = await self._get("/search", {"query": query})
        await self.cache.set(self.k_search(self._sig(query.strip().lower())), data, ttl=self.TTL_SEARCH)
        return data

    async def search_trending(self) -> Dict[str, Any]:
        data = await self._get("/search/trending")
        await self.cache.set(self.k_trending(), data, ttl=self.TTL_TRENDING)
        return data

    # Global
    async def global_data(self) -> Dict[str, Any]:
        data = await self._get("/global")
        await self.cache.set(self.k_global(), data, ttl=self.TTL_GLOBAL)
        return data

    async def global_defi(self) -> Dict[str, Any]:
        data = await self._get("/global/decentralized_finance_defi")
        await self.cache.set(self.k_global_defi(), data, ttl=self.TTL_GLOBAL_DEFI)
        return data

    # Public Treasury
    async def public_treasury(self, entity: str, coin_id: str) -> Dict[str, Any]:
        """
        entity: 'companies' | 'governments'
        Пример пути: /companies/public_treasury/bitcoin
        """
        path = f"/{entity}/public_treasury/{coin_id}"
        data = await self._get(path)
        await self.cache.set(self.k_public_treasury(entity, coin_id), data, ttl=self.TTL_PUBLIC_TREASURY)
        return data
