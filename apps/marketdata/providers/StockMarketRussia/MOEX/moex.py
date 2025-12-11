from typing import Any
import httpx
from enum import Enum

from apps.marketdata.providers.StockMarketRussia.MOEX.dto.engine_market_boards import MOEXBoards, parse_moex_boards
from apps.marketdata.providers.StockMarketRussia.MOEX.dto.engine_markets import MOEXEngineMarkets, parse_moex_markets
from apps.marketdata.providers.StockMarketRussia.MOEX.dto.engines import MOEXEngines, parse_moex_engines
from apps.marketdata.providers.StockMarketRussia.MOEX.dto.securities import MOEXSecurities, parse_moex_securities
from apps.marketdata.providers.provider import Provider
from apps.marketdata.services.redis_cache import RedisCacheService
from apps.marketdata.providers.StockMarketRussia.MOEX.cache_keys import MOEXCacheKeys
from apps.marketdata.providers.StockMarketRussia.MOEX.dto.security_detail import MOEXSecurityDetails, parse_moex_security_details

class MOEXProvider(Provider):
    """
        MOEX ISS API провайдер.
        - REST через httpx
        - Кладёт результаты в Redis (через RedisCacheService) с разумными TTL
    """
    Keys = MOEXCacheKeys

    # ===== Базовый префикс ключей =====
    KP = Keys.KP

    # ===== TTL по типам данных (сек) =====
    TTL_SECURITIES = 3600 * 6
    TTL_SECURITY_DETAIL = 3600 * 24
    TTL_ENGINES = 3600 * 24 * 30
    TTL_ENGINE_MARKETS = 3600 * 24 * 30
    TTL_ENGINE_MARKET_BOARDS = 3600 * 24 * 30

    BASE_URL = "http://iss.moex.com"

    def __init__(self, cache: RedisCacheService, timeout_s: float = 10.0) -> None:
        super().__init__(cache)
        self.timeout_s = timeout_s

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Базовый GET к MOEX ISS.

        При необходимости сюда можно добавить:
        - ретраи
        - логирование
        - собственные исключения по аналогии с CoinGecko
        """
        url = f"{self.BASE_URL}{path}"

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    # -----------------------------------------
    # 1. Справочники инструментов (legacy + 2.0)
    # -----------------------------------------

    async def securities(
            self,
            q: str | None = None,
            lang: str | None = None,
            engine: str | None = None,
            is_trading: int | None = None,
            market: str | None = None,
            group_by: str | None = None,
            limit: int | None = None,
            group_by_filter: str | None = None,
            start: int | None = None,
    ) -> MOEXSecurities:
        """
           Обёртка над /iss/securities.json
           Параметры один-в-один как в ISS:
           q               — поиск по части кода/названия/ISIN/EMITENT_ID/рег. номеру
           lang            — 'ru' (по умолчанию) или 'en'
           engine          — фильтр по движку (см. /iss/index.json?iss.only=trade_engines)
           is_trading      — 1 только торгуемые, 0 только неторгуемые
           market          — фильтр по рынку (см. /iss/index.json?iss.only=markets)
           group_by        — 'group' или 'type'
           limit           — 5, 10, 20, 100 (по умолчанию 100 на стороне MOEX)
           group_by_filter — значение group/type (в зависимости от group_by)
           start           — смещение (пагинация, отсчёт с 0)
       """
        params: dict[str, Any] = {}

        if q:
            params["q"] = q
        if lang:
            params["lang"] = lang
        if engine:
            params["engine"] = engine
        if is_trading is not None:
            params["is_trading"] = is_trading
        if market:
            params["market"] = market
        if group_by:
            params["group_by"] = group_by
        if limit is not None:
            params["limit"] = limit
        if group_by_filter:
            params["group_by_filter"] = group_by_filter
        if start is not None:
            params["start"] = start

        data = await self._get("/iss/securities.json", params=params)

        securities: MOEXSecurities = parse_moex_securities(data)

        key = self.Keys.securities(
            q=q,
            lang=lang,
            engine=engine,
            is_trading=is_trading,
            market=market,
            group_by=group_by,
            limit=limit,
            group_by_filter=group_by_filter,
            start=start
        )
        await self.cache.set(key, securities.to_redis_value(), ttl=self.TTL_SECURITIES)
        return securities

    async def security_detail(self, security: str, lang: str | None = None, primary_board: int | None = None, start: int | None = None) -> MOEXSecurityDetails:
        """
        Получить спецификацию инструмента.
        Например: https://iss.moex.com/iss/securities/IMOEX.xml
        """

        params = {
            "lang": lang,
            "primary_board": primary_board,
            "start": start,
        }
        data = await self._get(f"/iss/securities/{security}.json", params)

        security_detail: MOEXSecurityDetails = parse_moex_security_details(data)

        key = self.Keys.security_detail(security)
        await self.cache.set(key, security_detail.to_redis_value(), ttl=self.TTL_SECURITY_DETAIL)
        return security_detail

    # -----------------------------------------
    # 2. Структура рынка (engines / markets / boards)
    # -----------------------------------------

    async def engines(self) -> MOEXEngines:
        data = await self._get(f"/iss/engines.json")

        engines: MOEXEngines = parse_moex_engines(data)
        key = self.Keys.engines()

        await self.cache.set(key, engines.to_redis_value(), ttl=self.TTL_ENGINES)
        return engines

    async def engine_markets(self, engine: str = "stock") -> MOEXEngineMarkets:
        data = await self._get(f"/iss/engines/{engine}/markets")

        engine_markets: MOEXEngineMarkets = parse_moex_markets(data)
        key = self.Keys.engine_markets(engine)

        await self.cache.set(key, engine_markets.to_redis_value(), ttl=self.TTL_ENGINE_MARKETS)
        return engine_markets

    async def engine_market_boards(self, engine: str = "stock", market: str = "index") -> MOEXBoards:
        data = await self._get(f"/iss/engines/{engine}/markets/{market}/boards")

        boards: MOEXBoards = parse_moex_boards(data)
        key = self.Keys.engine_market_boards(engine, market)

        await self.cache.set(key, boards.to_redis_value(), ttl=self.TTL_ENGINE_MARKET_BOARDS)
        return boards

    # -----------------------------------------
    # 3. Текущие цены (по необходимым активам)
    # -----------------------------------------

    async def stock_index_SNDX_securities(self) -> None:
        pass


    class StockSharesBoards(str, Enum):
        TQBR = "TQBR"
        TQTF = "TQTF"
        TQTD = "TQTD"
        TQTE = "TQTE"
        TQIF = "TQIF"

    async def stock_shares_securities(self) -> None:
        pass

    class StockBondsBoards(str, Enum):
        TQCB = "TQCB"
        TQOB = "TQOB"

    async def stock_bonds_securities(self) -> None:
        pass

    async def currency_selt_CETS(self) -> None:
        pass






