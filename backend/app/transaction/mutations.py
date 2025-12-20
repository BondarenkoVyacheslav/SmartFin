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


@strawberry.type
class TransactionMutations:
    @strawberry.mutation
    def create_transaction(self, portfolio_id: int, asset_id: int, transaction_type: str, amount: float,
                           price: float = None) -> TransactionType:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        asset = Asset.objects.get(id=asset_id)
        return Transaction.objects.create(
            portfolio=portfolio,
            asset=asset,
            transaction_type=transaction_type,
            amount=amount,
            price=price
        )


    @strawberry.mutation
    def apply_manual_transaction(
            self,
            portfolio_id: int,
            asset_id: int,
            transaction_type: str, # "buy"/"sell"
            amount: str,
            price: str,
            source: str | None = "MANUAL",
    ) -> ApplyTransactionPayload:
        # 1) Валидация входа
        amount_d = _to_decimal(amount, "amount")
        price_d = _to_decimal(price, "price")

        if amount_d <= 0:
            raise ValidationError("amount must be > 0")
        if price_d <= 0:
            raise ValidationError("price must be > 0")
        if transaction_type not in ("buy", "sell"):
            raise ValidationError("transaction_type must be 'buy' or 'sell'")

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

            # Создаём запись транзакции (источник MANUAL сейчас у вас не хранится;
            # при желании добавишь поле source позже)
            tx = Transaction.objects.create(
                portfolio=portfolio,
                asset=asset,
                transaction_type=transaction_type,
                amount=amount_d,
                price=price_d,
                source=source
            )

            # Применяем к позиции
            if transaction_type == "buy":
                if position is None:
                    # OPEN (если позиции не было)
                    position = PortfolioAsset.objects.create(
                        portfolio=portfolio,
                        asset=asset,
                        quantity=amount_d,
                        avg_price=price_d,
                    )
                else:
                    # BUY MORE (пересчёт средневзвешенной)
                    old_qty = position.quantity
                    old_avg = position.avg_price or Decimal("0")
                    new_qty = old_qty + amount_d

                    # защита от деления на 0
                    if new_qty <= 0:
                        raise ValidationError("invalid quantity after buy")

                    new_avg = (old_qty * old_avg + amount_d * price_d) / new_qty

                    position.quantity = new_qty
                    position.avg_price = new_avg
                    position.save(update_fields=["quantity", "avg_price", "updated_at"])

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
            # avg_price обычно не меняют при sell (если модель учёта = average cost)
            position.save(update_fields=["quantity", "updated_at"])

            return ApplyTransactionPayload(transaction=tx, position=position)