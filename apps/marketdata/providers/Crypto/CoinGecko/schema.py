from __future__ import annotations

import json
from dataclasses import is_dataclass, fields
from typing import Any, List, Optional, Sequence, get_origin, get_args, Union

import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.coingecko import CoinGeckoProvider
from apps.marketdata.providers.Crypto.CoinGecko.cache_keys import CoinGeckoCacheKeys
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import SimplePriceEntry
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import SupportedVSCurrencies
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_list import CoinsList
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_markets import CoinsMarket
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_id import CoinDetail
from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_tickers import CoinTickers
from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_history import CoinHistory
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges import Exchanges
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges_list import ExchangesList
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_detail import Exchange
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_tickers import ExchangeTickers
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_volume_chart import ExchangeVolumeChart
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives import Derivatives
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchanges import DerivativesExchangesPage
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchanges_list import DerivativesExchangesList
from apps.marketdata.providers.Crypto.CoinGecko.dto.derivatives_exchange_detail import DerivativesExchangeDetails
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_rates import ExchangeRates
from apps.marketdata.providers.Crypto.CoinGecko.dto.search import SearchResult
from apps.marketdata.providers.Crypto.CoinGecko.dto.search_trending import SearchTrendingResult
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_data import GlobalData
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_defi import GlobalDefiData
from apps.marketdata.providers.Crypto.CoinGecko.dto.ping import Ping
from apps.marketdata.services.redis_cache import RedisCacheService, get_redis_cache


# === Ленивая инициализация CoinGeckoProvider с общим RedisCacheService ===

_coingecko: Optional[CoinGeckoProvider] = None


async def get_coingecko_provider() -> CoinGeckoProvider:
    """
    Единая точка получения CoinGeckoProvider:
    - берём глобальный RedisCacheService через get_redis_cache()
    - создаём провайдера один раз и переиспользуем
    """
    global _coingecko
    if _coingecko is None:
        cache: RedisCacheService = await get_redis_cache()
        _coingecko = CoinGeckoProvider(cache=cache)
    return _coingecko


# === Утилиты для восстановления DTO из JSON/строки, лежащей в Redis ===

def _build_dataclass(cls, data: Any):
    """
    Рекурсивно восстанавливает dataclass (в том числе вложенные списки dataclass-ов)
    из словаря, полученного из JSON.
    """
    if data is None:
        return None
    if not is_dataclass(cls):
        # Для примитивов/не dataclass-типов просто возвращаем данные как есть.
        return data

    kwargs = {}
    for f in fields(cls):
        name = f.name
        value = data.get(name)
        if value is None:
            kwargs[name] = None
            continue

        field_type = f.type
        origin = get_origin(field_type)
        args = get_args(field_type)

        # List[...] или Sequence[...]
        if origin in (list, List, Sequence):
            inner_type = args[0] if args else Any
            if is_dataclass(inner_type):
                kwargs[name] = [
                    _build_dataclass(inner_type, item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                kwargs[name] = value
            continue

        # Optional[Dataclass] / Union[Dataclass, ...]
        if origin is Union and args:
            dc_arg = next((a for a in args if is_dataclass(a)), None)
            if dc_arg is not None and isinstance(value, dict):
                kwargs[name] = _build_dataclass(dc_arg, value)
                continue

        # Вложенный dataclass
        if is_dataclass(field_type) and isinstance(value, dict):
            kwargs[name] = _build_dataclass(field_type, value)
        else:
            kwargs[name] = value

    return cls(**kwargs)


def _hydrate_from_redis(dto_cls, raw: Any):
    """
    Универсальная функция восстановления DTO из значения, лежащего в Redis.

    Приоритет:
    1) Если у dto_cls есть from_redis_value и raw — str, используем её.
    2) Иначе пробуем generic-восстановление через json.loads + _build_dataclass.
    """
    if raw is None:
        return None

    # 1. Если у DTO есть свой from_redis_value — даём ему шанс первым.
    from_redis = getattr(dto_cls, "from_redis_value", None)
    if isinstance(raw, str) and callable(from_redis):
        try:
            # Все твои to_redis_value возвращают JSON-строку,
            # RedisCacheService.set кладёт её как json-строку,
            # get() возвращает её как Python-строку (результат json.loads),
            # так что её можно напрямую отдавать from_redis_value.
            return from_redis(raw)
        except Exception:
            # Если вдруг формат изменился/сломался — тихо падаем в generic-путь.
            pass

    # 2. Generic-ветка

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return None
    elif isinstance(raw, dict):
        data = raw
    else:
        # Для нестандартных форматов (list, etc.) здесь ничего не делаем,
        # такие кейсы обрабатываются отдельно (как simple_price).
        return None

    try:
        return _build_dataclass(dto_cls, data)
    except Exception:
        return None


@strawberry.type
class CoinGeckoQuery:
    # ---- /ping ----
    @strawberry.field
    async def ping(self) -> Optional[Ping]:
        """
        /ping — простой health-check CoinGecko.
        """
        cg = await get_coingecko_provider()
        return await cg.ping()

    # ---- /simple/price ----
    @strawberry.field
    async def simple_price(
        self,
        ids: List[str],
        vs_currencies: List[str],
        include_market_cap: bool = False,
        include_24hr_vol: bool = False,
        include_24hr_change: bool = False,
        include_last_updated_at: bool = False,
    ) -> List[SimplePriceEntry]:
        """
        Обёртка над /simple/price.

        1. Пытаемся достать список SimplePriceEntry из Redis.
        2. Если нет/ошибка — обращаемся к CoinGeckoProvider.simple_price(...)
           (он сам положит свежие данные в кэш).
        """
        cg = await get_coingecko_provider()

        ids_csv = cg._csv(ids)
        vs_csv = cg._csv(vs_currencies)

        key = CoinGeckoCacheKeys.simple_price(
            ids_sig=cg._sig(ids_csv),
            vs_sig=cg._sig(vs_csv),
            opts_sig=cg._sig(
                "mc" if include_market_cap else "nomc",
                "vol" if include_24hr_vol else "novol",
                "chg" if include_24hr_change else "nochg",
                "ts" if include_last_updated_at else "nots",
            ),
        )

        cached = await cg.cache.get(key)
        if isinstance(cached, list):
            try:
                return [
                    SimplePriceEntry(**row)
                    for row in cached
                    if isinstance(row, dict)
                ]
            except Exception:
                # если формат неожиданный — тихо падаем в провайдера
                pass

        # Кэш пустой или невалидный — берём из провайдера (он же обновит кэш).
        return await cg.simple_price(
            ids=ids,
            vs_currencies=vs_currencies,
            include_market_cap=include_market_cap,
            include_24hr_vol=include_24hr_vol,
            include_24hr_change=include_24hr_change,
            include_last_updated_at=include_last_updated_at,
        )

    # ---- /simple/supported_vs_currencies ----
    @strawberry.field
    async def supported_vs_currencies(self) -> SupportedVSCurrencies:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.supported_vs()
        cached = await cg.cache.get(key)

        dto = _hydrate_from_redis(SupportedVSCurrencies, cached)
        if dto is not None:
            return dto

        return await cg.simple_supported_vs_currencies()

    # ---- /coins/list ----
    @strawberry.field
    async def coins_list(self, include_platform: bool = False) -> CoinsList:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.coins_list(include_platform)
        cached = await cg.cache.get(key)

        dto = _hydrate_from_redis(CoinsList, cached)
        if dto is not None:
            return dto

        return await cg.coins_list(include_platform=include_platform)

    # ---- /coins/markets ----
    @strawberry.field
    async def coins_markets(
        self,
        vs_currency: str,
        ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        order: str = "market_cap_desc",
        per_page: int = 250,
        page: int = 1,
        sparkline: bool = False,
        price_change_percentage: str = "1h,24h,7d",
        locale: Optional[str] = None,
    ) -> CoinsMarket:
        cg = await get_coingecko_provider()

        params: dict[str, Any] = {
            "vs_currency": vs_currency.lower(),
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower(),
            "price_change_percentage": price_change_percentage,
        }
        if ids:
            params["ids"] = cg._csv(ids)
        if category:
            params["category"] = category
        if locale:
            params["locale"] = locale

        key = CoinGeckoCacheKeys.coins_markets(
            vs=vs_currency,
            page=page,
            order=order,
            spark=sparkline,
            pcp=price_change_percentage,
            ids_sig=cg._sig(params["ids"]) if "ids" in params else None,
            category=category,
        )

        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(CoinsMarket, cached)
        if dto is not None:
            return dto

        return await cg.coins_markets(
            vs_currency=vs_currency,
            ids=ids,
            category=category,
            order=order,
            per_page=per_page,
            page=page,
            sparkline=sparkline,
            price_change_percentage=price_change_percentage,
            locale=locale,
        )

    # ---- /coins/{id} ----
    @strawberry.field
    async def coin_detail(
        self,
        coin_id: str,
        localization: bool = False,
        tickers: bool = True,
        market_data: bool = True,
        community_data: bool = True,
        developer_data: bool = True,
        sparkline: bool = False,
    ) -> CoinDetail:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.coin_detail(coin_id)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(CoinDetail, cached)
        if dto is not None:
            return dto

        return await cg.coin_detail(
            coin_id=coin_id,
            localization=localization,
            tickers=tickers,
            market_data=market_data,
            community_data=community_data,
            developer_data=developer_data,
            sparkline=sparkline,
        )

    # ---- /coins/{id}/tickers ----
    @strawberry.field
    async def coin_tickers(
        self,
        coin_id: str,
        page: int = 1,
        exchange_ids: Optional[str] = None,
        include_exchange_logo: bool = True,
        order: str = "trust_score_desc",
        depth: bool = False,
    ) -> CoinTickers:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.coin_tickers(coin_id, page)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(CoinTickers, cached)
        if dto is not None:
            return dto

        # Используем строковый order, маппим в Enum провайдера при необходимости
        order_enum = cg.OrderEnum(order) if isinstance(order, str) else order

        return await cg.coin_tickers(
            coin_id=coin_id,
            page=page,
            exchange_ids=exchange_ids,
            include_exchange_logo=include_exchange_logo,
            order=order_enum,
            depth=depth,
        )

    # ---- /coins/{id}/history ----
    @strawberry.field
    async def coin_history(
        self,
        coin_id: str,
        date_ddmmyyyy: str,
        localization: bool = False,
    ) -> CoinHistory:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.coin_history(coin_id, date_ddmmyyyy, localization)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(CoinHistory, cached)
        if dto is not None:
            return dto

        return await cg.coin_history(
            coin_id=coin_id,
            date_ddmmyyyy=date_ddmmyyyy,
            localization=localization,
        )

    # ---- /exchanges ----
    @strawberry.field
    async def exchanges(
        self,
        per_page: int = 250,
        page: int = 1,
    ) -> Exchanges:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchanges(page)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(Exchanges, cached)
        if dto is not None:
            return dto

        return await cg.exchanges(per_page=per_page, page=page)

    # ---- /exchanges/list ----
    @strawberry.field
    async def exchanges_list(self) -> ExchangesList:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchanges_list()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(ExchangesList, cached)
        if dto is not None:
            return dto

        return await cg.exchanges_list()

    # ---- /exchanges/{id} ----
    @strawberry.field
    async def exchange_detail(self, ex_id: str) -> Exchange:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchange_detail(ex_id)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(Exchange, cached)
        if dto is not None:
            return dto

        return await cg.exchange_detail(ex_id=ex_id)

    # ---- /exchanges/{id}/tickers ----
    @strawberry.field
    async def exchange_tickers(
        self,
        ex_id: str,
        page: int = 1,
        coin_ids: Optional[str] = None,
        depth: bool = False,
        order: str = "trust_score_desc",
    ) -> ExchangeTickers:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchange_tickers(ex_id, page)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(ExchangeTickers, cached)
        if dto is not None:
            return dto

        order_enum = cg.ExchangeTickersOrderEnum(order) if isinstance(order, str) else order

        return await cg.exchange_tickers(
            ex_id=ex_id,
            page=page,
            coin_ids=coin_ids,
            depth=depth,
            order=order_enum,
        )

    # ---- /exchanges/{id}/volume_chart ----
    @strawberry.field
    async def exchange_volume_chart(
        self,
        ex_id: str,
        days: int = 1,
    ) -> ExchangeVolumeChart:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchange_volume_chart(ex_id, days)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(ExchangeVolumeChart, cached)
        if dto is not None:
            return dto

        return await cg.exchange_volume_chart(ex_id=ex_id, days=days)

    # ---- /derivatives ----
    @strawberry.field
    async def derivatives(self) -> Derivatives:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.derivatives()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(Derivatives, cached)
        if dto is not None:
            return dto

        return await cg.derivatives()

    # ---- /derivatives/exchanges ----
    @strawberry.field
    async def derivatives_exchanges(
        self,
        per_page: int = 250,
        page: int = 1,
    ) -> DerivativesExchangesPage:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.derivatives_exchanges(page)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(DerivativesExchangesPage, cached)
        if dto is not None:
            return dto

        return await cg.derivatives_exchanges(per_page=per_page, page=page)

    # ---- /derivatives/exchanges/{id} ----
    @strawberry.field
    async def derivatives_exchange_detail(self, ex_id: str) -> DerivativesExchangeDetails:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.derivatives_exchange_detail(ex_id)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(DerivativesExchangeDetails, cached)
        if dto is not None:
            return dto

        return await cg.derivatives_exchange_detail(ex_id=ex_id)

    # ---- /derivatives/exchanges/list ----
    @strawberry.field
    async def derivatives_exchanges_list(self) -> DerivativesExchangesList:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.derivatives_exchanges_list()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(DerivativesExchangesList, cached)
        if dto is not None:
            return dto

        return await cg.derivatives_exchanges_list()

    # ---- /exchange_rates ----
    @strawberry.field
    async def exchange_rates(self) -> ExchangeRates:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.exchange_rates()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(ExchangeRates, cached)
        if dto is not None:
            return dto

        return await cg.exchange_rates()

    # ---- /search ----
    @strawberry.field
    async def search(self, query: str) -> SearchResult:
        cg = await get_coingecko_provider()
        sig = cg._sig(query.strip().lower())
        key = CoinGeckoCacheKeys.search(sig)
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(SearchResult, cached)
        if dto is not None:
            return dto

        return await cg.search(query=query)

    # ---- /search/trending ----
    @strawberry.field
    async def search_trending(self) -> SearchTrendingResult:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.trending()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(SearchTrendingResult, cached)
        if dto is not None:
            return dto

        return await cg.search_trending()

    # ---- /global ----
    @strawberry.field(name="global")
    async def global_data(self) -> GlobalData:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.global_data()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(GlobalData, cached)
        if dto is not None:
            return dto

        return await cg.global_data()

    # ---- /global/decentralized_finance_defi ----
    @strawberry.field
    async def global_defi(self) -> GlobalDefiData:
        cg = await get_coingecko_provider()
        key = CoinGeckoCacheKeys.global_defi()
        cached = await cg.cache.get(key)
        dto = _hydrate_from_redis(GlobalDefiData, cached)
        if dto is not None:
            return dto

        return await cg.global_defi()


schema = strawberry.Schema(query=CoinGeckoQuery)
