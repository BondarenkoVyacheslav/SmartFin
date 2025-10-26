# apps/core/models.py
from django.db import models

# Python-choices на основе БД ENUM (ядро — схема "core")
# Эти перечисления удобно использовать в ORM и валидации,
# даже если сейчас таблицы с ними — unmanaged в других app’ах.

class AssetClass(models.TextChoices):
    STOCK = "stock", "Stock"
    BOND = "bond", "Bond"
    FUND = "fund", "Fund"
    CRYPTO = "crypto", "Crypto"
    FIAT = "fiat", "Fiat"
    METAL = "metal", "Metal"
    CASH = "cash", "Cash"
    DEPOSIT = "deposit", "Deposit"
    OTHER = "other", "Other"

class TransactionType(models.TextChoices):
    BUY = "buy", "Buy"
    SELL = "sell", "Sell"
    DEPOSIT = "deposit", "Deposit"
    WITHDRAW = "withdraw", "Withdraw"
    TRANSFER_IN = "transfer_in", "Transfer In"
    TRANSFER_OUT = "transfer_out", "Transfer Out"
    DIVIDEND = "dividend", "Dividend"
    COUPON = "coupon", "Coupon"
    INTEREST = "interest", "Interest"
    FEE = "fee", "Fee"
    SPLIT = "split", "Split"
    MERGE = "merge", "Merge"
    ADJUSTMENT = "adjustment", "Adjustment"

class PriceInterval(models.TextChoices):
    TICK = "tick", "Tick"
    MIN = "min", "Minute"
    HOUR = "hour", "Hour"
    DAY = "day", "Day"

# Опционально: поле, которое мапится на PostgreSQL ENUM (core.*)
# Можно использовать в будущих managed-моделях, если захочешь создавать таблицы через Django.
class PostgresEnumField(models.Field):
    description = "PostgreSQL enum in the core schema"

    def __init__(self, enum_name: str, *args, **kwargs):
        # передаём choices снаружи, чтобы Django валидировал значения
        self.enum_name = enum_name  # например: "core.asset_class_enum"
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["enum_name"] = self.enum_name
        return name, path, args, kwargs

    def db_type(self, connection):
        # Возвращаем fully-qualified имя типа
        return self.enum_name

    def get_prep_value(self, value):
        return None if value is None else str(value)

    def from_db_value(self, value, expression, connection):
        return value

class AssetClassEnumField(PostgresEnumField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", AssetClass.choices)
        super().__init__("core.asset_class_enum", *args, **kwargs)

class TransactionTypeEnumField(PostgresEnumField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", TransactionType.choices)
        super().__init__("core.transaction_type_enum", *args, **kwargs)

class PriceIntervalEnumField(PostgresEnumField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", PriceInterval.choices)
        super().__init__("core.price_interval_enum", *args, **kwargs)
