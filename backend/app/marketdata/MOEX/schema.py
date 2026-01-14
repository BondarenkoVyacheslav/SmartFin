from __future__ import annotations

from typing import Optional

import strawberry

from app.marketdata.MOEX.cache_keys import MOEXCacheKeys
from app.marketdata.MOEX.dto.currency_selt_CETS_securities import (
    MOEXCurrencySeltCETSSecurities,
)
from app.marketdata.MOEX.dto.engine_market_boards import MOEXBoards
from app.marketdata.MOEX.dto.engine_markets import MOEXEngineMarkets
from app.marketdata.MOEX.dto.engines import MOEXEngines
from app.marketdata.MOEX.dto.securities import MOEXSecurities
from app.marketdata.MOEX.dto.security_detail import MOEXSecurityDetails
from app.marketdata.MOEX.dto.stock_bonds_TQCB_securities import (
    MOEXStockBondsTQCBSecurities,
)
from app.marketdata.MOEX.dto.stock_bonds_TQOB_securities import (
    MOEXStockBondsTQOBSecuritiesResponse,
)
from app.marketdata.MOEX.dto.stock_index_SNDX_securities import (
    MOEXStockIndexSndxSecurities,
)
from app.marketdata.MOEX.dto.stock_shares_TQBR_securities import (
    MOEXSharesTQBRSecurities,
)
from app.marketdata.MOEX.dto.stock_shares_TQTF_securities import (
    MOEXStockSharesTQTFSecurities,
)
from app.marketdata.MOEX.moex import MOEXProvider
from app.marketdata.services.redis_cache import RedisCacheService


@strawberry.type
class MOEXQuery:
    def __init__(self, moex_provider: MOEXProvider, cache: RedisCacheService):
        self.moex_provider = moex_provider
        self.cache = cache

    # ---- /iss/securities.json ----
    @strawberry.field
    async def securities(
        self,
        q: Optional[str] = None,
        lang: Optional[str] = None,
        engine: Optional[str] = None,
        is_trading: Optional[int] = None,
        market: Optional[str] = None,
        group_by: Optional[str] = None,
        limit: Optional[int] = None,
        group_by_filter: Optional[str] = None,
        start: Optional[int] = None,
    ) -> MOEXSecurities:
        key = MOEXCacheKeys.securities(
            q=q,
            lang=lang,
            engine=engine,
            is_trading=is_trading,
            market=market,
            group_by=group_by,
            limit=limit,
            group_by_filter=group_by_filter,
            start=start,
        )

        cached = await self.cache.get(key)
        dto = MOEXSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.securities(
            q=q,
            lang=lang,
            engine=engine,
            is_trading=is_trading,
            market=market,
            group_by=group_by,
            limit=limit,
            group_by_filter=group_by_filter,
            start=start,
        )

    # ---- /iss/securities/{security}.json ----
    @strawberry.field
    async def security_detail(
        self,
        security: str,
        lang: Optional[str] = None,
        primary_board: Optional[int] = None,
        start: Optional[int] = None,
    ) -> MOEXSecurityDetails:
        key = MOEXCacheKeys.security_detail(security)
        cached = await self.cache.get(key)
        dto = MOEXSecurityDetails.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.security_detail(
            security=security,
            lang=lang,
            primary_board=primary_board,
            start=start,
        )

    # ---- /iss/engines.json ----
    @strawberry.field
    async def engines(self) -> MOEXEngines:
        key = MOEXCacheKeys.engines()
        cached = await self.cache.get(key)
        dto = MOEXEngines.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.engines()

    # ---- /iss/engines/{engine}/markets ----
    @strawberry.field
    async def engine_markets(self, engine: str = "stock") -> MOEXEngineMarkets:
        key = MOEXCacheKeys.engine_markets(engine)
        cached = await self.cache.get(key)
        dto = MOEXEngineMarkets.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.engine_markets(engine=engine)

    # ---- /iss/engines/{engine}/markets/{market}/boards ----
    @strawberry.field
    async def engine_market_boards(
        self,
        engine: str = "stock",
        market: str = "index",
    ) -> MOEXBoards:
        key = MOEXCacheKeys.engine_market_boards(engine, market)
        cached = await self.cache.get(key)
        dto = MOEXBoards.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.engine_market_boards(
            engine=engine,
            market=market,
        )

    # ---- /iss/engines/stock/markets/index/boards/SNDX/securities ----
    @strawberry.field
    async def stock_index_SNDX_securities(
        self,
        securities: str = "IMOEX,MOEXBMI,MOEX10,MOEXOG,MOEXFN,MOEXMM,MOEXCN,RGBI,RUCBITR,MOEXREPO",
    ) -> MOEXStockIndexSndxSecurities:
        key = MOEXCacheKeys.stock_index_SNDX_securities()
        cached = await self.cache.get(key)
        dto = MOEXStockIndexSndxSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.stock_index_SNDX_securities(
            securities=securities,
        )

    # ---- /iss/engines/stock/markets/shares/boards/TQBR/securities ----
    @strawberry.field
    async def stock_shares_TQBR_securities(
        self,
        securities: Optional[str] = None,
    ) -> MOEXSharesTQBRSecurities:
        key = MOEXCacheKeys.stock_shares_TQBR_securities(securities)
        cached = await self.cache.get(key)
        dto = MOEXSharesTQBRSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.stock_shares_TQBR_securities(
            securities=securities,
        )

    # ---- /iss/engines/stock/markets/shares/boards/TQTF/securities ----
    @strawberry.field
    async def stock_shares_TQTF_securities(
        self,
        securities: Optional[str] = None,
    ) -> MOEXStockSharesTQTFSecurities:
        key = MOEXCacheKeys.stock_shares_TQTF_securities(securities)
        cached = await self.cache.get(key)
        dto = MOEXStockSharesTQTFSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.stock_shares_TQTF_securities(
            securities=securities,
        )

    # ---- /iss/engines/stock/markets/bonds/boards/TQCB/securities ----
    @strawberry.field
    async def stock_bonds_TQCB_securities(
        self,
        securities: Optional[str] = None,
    ) -> MOEXStockBondsTQCBSecurities:
        key = MOEXCacheKeys.stock_bonds_TQCB_securities(securities)
        cached = await self.cache.get(key)
        dto = MOEXStockBondsTQCBSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.stock_bonds_TQCB_securities(
            securities=securities,
        )

    # ---- /iss/engines/stock/markets/bonds/boards/TQOB/securities ----
    @strawberry.field
    async def stock_bonds_TQOB_securities(
        self,
        securities: Optional[str] = None,
    ) -> MOEXStockBondsTQOBSecuritiesResponse:
        key = MOEXCacheKeys.stock_bound_TQOB_securities(securities)
        cached = await self.cache.get(key)
        dto = MOEXStockBondsTQOBSecuritiesResponse.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.stock_bonds_TQOB_securities(
            securities=securities,
        )

    # ---- /iss/engines/currency/markets/selt/boards/CETS/securities ----
    @strawberry.field
    async def currency_selt_CETS_securities(
        self,
        securities: Optional[str] = None,
    ) -> MOEXCurrencySeltCETSSecurities:
        key = MOEXCacheKeys.currency_selt_CETS_securities(securities)
        cached = await self.cache.get(key)
        dto = MOEXCurrencySeltCETSSecurities.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.moex_provider.currency_selt_CETS_securities(
            securities=securities,
        )
