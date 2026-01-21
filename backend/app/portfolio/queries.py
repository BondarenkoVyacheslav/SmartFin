from decimal import Decimal
from typing import List, Optional

import strawberry
from strawberry import auto

from app.assets.queries import AssetTypeGQL
from app.marketdata import market_data_api
from .models import Portfolio, PortfolioAsset


@strawberry.django.type(Portfolio)
class PortfolioType:
    id: auto
    user_id: auto
    name: auto
    created_at: auto
    portfolio_asset: List[AssetTypeGQL]


@strawberry.django.type(PortfolioAsset)
class PortfolioAssetType:
    id: auto
    asset: AssetTypeGQL
    portfolio: PortfolioType
    quantity: auto
    avg_buy_price: auto
    buy_currency: auto
    updated_at: auto


@strawberry.type
class PortfolioAssetPositionGQL:
    asset: AssetTypeGQL
    quantity: float
    avg_buy_price: Optional[float]
    buy_currency: Optional[str]
    balance: Optional[float]
    share_percent: Optional[float]


@strawberry.type
class PortfolioAssetTypeSummaryGQL:
    portfolio_id: int
    asset_type_id: int
    base_currency: str
    total_balance: float
    positions: List[PortfolioAssetPositionGQL]


def _normalize_currency(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return code.strip().upper()


def _to_decimal(value: Optional[float | Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _maybe_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


@strawberry.type
class PortfolioQueries:
    portfolios: List[PortfolioType] = strawberry.django.field()
    portfolio_assets: List[PortfolioAssetType] = strawberry.django.field()

    @strawberry.field
    def portfolio_positions_by_asset_type(
        self,
        info,
        portfolio_id: int,
        asset_type_id: int,
    ) -> PortfolioAssetTypeSummaryGQL:
        user = info.context.request.user
        if not user or not user.is_authenticated:
            raise ValueError("Authentication required")

        try:
            portfolio = Portfolio.objects.only("id", "user_id", "base_currency").get(id=portfolio_id)
        except Portfolio.DoesNotExist as exc:
            raise ValueError("Portfolio not found") from exc

        if portfolio.user_id != user.id:
            raise ValueError("Portfolio not found")

        positions = list(
            PortfolioAsset.objects.select_related("asset", "asset__asset_type")
            .filter(portfolio_id=portfolio_id, asset__asset_type_id=asset_type_id)
        )

        base_currency = _normalize_currency(portfolio.base_currency) or ""

        currencies = {
            _normalize_currency(p.buy_currency or p.asset.currency)
            for p in positions
            if _normalize_currency(p.buy_currency or p.asset.currency) not in {None, base_currency}
        }
        pairs = [f"{ccy}/{base_currency}" for ccy in sorted(currencies)]
        fx_rates = market_data_api.get_fx_rates(pairs) if pairs else {}

        def resolve_rate(currency: Optional[str]) -> Optional[Decimal]:
            normalized = _normalize_currency(currency)
            if not normalized or normalized == base_currency:
                return Decimal("1")
            pair = f"{normalized}/{base_currency}"
            rate = fx_rates.get(pair) or fx_rates.get(pair.upper()) or fx_rates.get(pair.lower())
            return _to_decimal(rate)

        items: List[PortfolioAssetPositionGQL] = []
        total_balance = Decimal("0")
        balances: List[Optional[Decimal]] = []

        for position in positions:
            avg_buy_price = _to_decimal(position.avg_buy_price)
            quantity = _to_decimal(position.quantity) or Decimal("0")
            currency = _normalize_currency(position.buy_currency or position.asset.currency)
            rate = resolve_rate(currency)

            balance: Optional[Decimal] = None
            if avg_buy_price is not None and rate is not None:
                balance = quantity * avg_buy_price * rate
                total_balance += balance
            balances.append(balance)

            items.append(
                PortfolioAssetPositionGQL(
                    asset=position.asset,
                    quantity=float(quantity),
                    avg_buy_price=_maybe_float(avg_buy_price),
                    buy_currency=currency,
                    balance=_maybe_float(balance),
                    share_percent=None,
                )
            )

        if total_balance > 0:
            for item, balance in zip(items, balances, strict=True):
                if balance is None:
                    continue
                item.share_percent = float((balance / total_balance) * Decimal("100"))

        return PortfolioAssetTypeSummaryGQL(
            portfolio_id=portfolio_id,
            asset_type_id=asset_type_id,
            base_currency=base_currency,
            total_balance=float(total_balance),
            positions=items,
        )
