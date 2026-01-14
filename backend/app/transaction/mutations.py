import strawberry
from .models import Transaction
from app.portfolio.models import Portfolio, PortfolioAsset
from app.assets.models import Asset
from .queries import TransactionType
from app.portfolio.queries import PortfolioAssetType
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction


@strawberry.type
class ApplyTransactionPayload:
    transaction: TransactionType
    position: PortfolioAssetType | None  # при полном закрытии вернём None

def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{field_name} must be a decimal string")
    return d


def _normalize_currency(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if not code:
        raise ValidationError(f"{field_name} must be a non-empty string")
    return code


def _validate_action(
    action: str | None,
    transaction_type: str,
    position: PortfolioAsset | None,
    amount: Decimal,
) -> None:
    if action is None:
        return
    if action == "OPEN":
        if transaction_type != "buy":
            raise ValidationError("OPEN action requires transaction_type='buy'")
        if position is not None:
            raise ValidationError("OPEN action requires no existing position")
        return
    if action == "CLOSE":
        if transaction_type != "sell":
            raise ValidationError("CLOSE action requires transaction_type='sell'")
        if position is None:
            raise ValidationError("CLOSE action requires an existing position")
        if amount != position.quantity:
            raise ValidationError("CLOSE action requires amount == position quantity")
        return
    if action == "BUY_MORE":
        if transaction_type != "buy":
            raise ValidationError("BUY_MORE action requires transaction_type='buy'")
        if position is None:
            raise ValidationError("BUY_MORE action requires an existing position")
        return
    if action == "SELL_PART":
        if transaction_type != "sell":
            raise ValidationError("SELL_PART action requires transaction_type='sell'")
        if position is None:
            raise ValidationError("SELL_PART action requires an existing position")
        if amount >= position.quantity:
            raise ValidationError("SELL_PART action requires amount < position quantity")
        return
    raise ValidationError("action must be one of: OPEN, CLOSE, BUY_MORE, SELL_PART")


@strawberry.type
class TransactionMutations:
    @strawberry.mutation
    def create_transaction(
        self,
        portfolio_id: int,
        asset_id: int,
        transaction_type: str,
        amount: float,
        price: float | None = None,
        price_currency: str | None = None,
        source: str | None = "MANUAL",
                           ) -> TransactionType:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        asset = Asset.objects.get(id=asset_id)
        return Transaction.objects.create(
            portfolio=portfolio,
            asset=asset,
            transaction_type=transaction_type,
            amount=amount,
            price=price,
            price_currency=_normalize_currency(price_currency, "price_currency"),
            source=source,
        )


    @strawberry.mutation
    def apply_manual_transaction(
            self,
            portfolio_id: int,
            asset_id: int,
            transaction_type: str, # "buy"/"sell"
            amount: str,
            price: str | None = None,
            price_currency: str | None = None,
            source: str | None = "MANUAL",
            action: str | None = None,
    ) -> ApplyTransactionPayload:
        # 1) Валидация входа
        amount_d = _to_decimal(amount, "amount")
        price_d = _to_decimal(price, "price") if price is not None else None
        price_currency = _normalize_currency(price_currency, "price_currency")
        if price_d is None and price_currency is not None:
            raise ValidationError("price is required when price_currency is provided")
        if price_d is not None and price_currency is None:
            raise ValidationError("price_currency is required when price is provided")

        if amount_d <= 0:
            raise ValidationError("amount must be > 0")
        if price_d is not None and price_d <= 0:
            raise ValidationError("price must be > 0")
        if transaction_type not in ("buy", "sell"):
            raise ValidationError("transaction_type must be 'buy' or 'sell'")
        if transaction_type == "buy" and price_d is None:
            raise ValidationError("price and price_currency are required for buys")
        valid_sources = {choice[0] for choice in Transaction.SOURCE_TYPES}
        if source not in valid_sources:
            raise ValidationError(f"source must be one of: {', '.join(sorted(valid_sources))}")
        action = action.strip().upper() if action is not None else None

        # 2) Атомарно: создать транзакцию + обновить позицию
        with db_transaction.atomic():
            portfolio = Portfolio.objects.get(id=portfolio_id)
            asset = Asset.objects.get(id=asset_id)

            # Блокируем строку позиции, если она есть (защита от гонок)
            position = (
                PortfolioAsset.objects.select_for_update()
                .filter(portfolio=portfolio, asset=asset)
                .first()
            )

            _validate_action(action, transaction_type, position, amount_d)

            if price_currency and position and position.buy_currency and price_currency != position.buy_currency:
                raise ValidationError("price_currency must match position buy_currency")

            # Создаём запись транзакции
            tx = Transaction.objects.create(
                portfolio=portfolio,
                asset=asset,
                transaction_type=transaction_type,
                amount=amount_d,
                price=price_d,
                price_currency=price_currency,
                source=source,
            )

            # Применяем к позиции
            if transaction_type == "buy":
                if position is None:
                    # OPEN (если позиции не было)
                    position = PortfolioAsset.objects.create(
                        portfolio=portfolio,
                        asset=asset,
                        quantity=amount_d,
                        avg_buy_price=price_d,
                        buy_currency=price_currency,
                    )
                else:
                    # BUY MORE
                    if position.avg_buy_price is None or position.buy_currency is None:
                        raise ValidationError("position is missing avg_buy_price or buy_currency")
                    current_qty = position.quantity
                    new_qty = current_qty + amount_d

                    # защита от деления на 0
                    if new_qty <= 0:
                        raise ValidationError("invalid quantity after buy")

                    position.quantity = new_qty
                    position.avg_buy_price = (
                        (position.avg_buy_price * current_qty + price_d * amount_d) / new_qty
                    )
                    position.save(update_fields=["quantity", "avg_buy_price", "updated_at"])

                return ApplyTransactionPayload(transaction=tx, position=position)

            # SELL ветка
            if position is None:
                raise ValidationError("Cannot sell: position does not exist")

            if amount_d > position.quantity:
                raise ValidationError("Cannot sell more than current position quantity")

            new_qty = position.quantity - amount_d

            if new_qty == 0:
                # CLOSE
                position.delete()
                return ApplyTransactionPayload(transaction=tx, position=None)

            # SELL PART
            position.quantity = new_qty
            position.save(update_fields=["quantity", "updated_at"])

            return ApplyTransactionPayload(transaction=tx, position=position)
