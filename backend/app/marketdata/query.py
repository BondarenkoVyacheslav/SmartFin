from __future__ import annotations

from typing import List, Optional

import strawberry

from app.marketdata.router import AssetPriceRequest, MarketDataRouter


@strawberry.type
class MarketDataAssetPrice:
    asset_type: str
    symbol: str
    price: Optional[float]
    currency: Optional[str]


@strawberry.input
class MarketDataAssetPriceRequest:
    asset_type: str
    symbol: str
    currency: Optional[str] = None


@strawberry.type
class MarketDataQueries:
    @strawberry.field
    async def asset_price(
        self,
        asset_type: str,
        symbol: str,
        currency: Optional[str] = None,
    ) -> MarketDataAssetPrice:
        router = MarketDataRouter()
        try:
            result = await router.get_price(
                AssetPriceRequest(
                    asset_type=asset_type,
                    symbol=symbol,
                    currency=currency,
                )
            )
        finally:
            await router.aclose()

        return MarketDataAssetPrice(
            asset_type=result.asset_type,
            symbol=result.symbol,
            price=result.price,
            currency=result.currency,
        )

    @strawberry.field
    async def asset_prices(
        self,
        requests: List[MarketDataAssetPriceRequest],
    ) -> List[MarketDataAssetPrice]:
        if not requests:
            return []

        router = MarketDataRouter()
        try:
            results = await router.get_prices(
                [
                    AssetPriceRequest(
                        asset_type=req.asset_type,
                        symbol=req.symbol,
                        currency=req.currency,
                    )
                    for req in requests
                ]
            )
        finally:
            await router.aclose()

        return [
            MarketDataAssetPrice(
                asset_type=result.asset_type,
                symbol=result.symbol,
                price=result.price,
                currency=result.currency,
            )
            for result in results
        ]
