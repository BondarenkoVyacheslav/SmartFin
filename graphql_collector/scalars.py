# config/graphql_collector/scalars.py
import datetime as dt
from decimal import Decimal, InvalidOperation
import strawberry

@strawberry.scalar(description="Arbitrary-precision decimal as string")
def DecimalScalar(value: Decimal) -> str:
    # serialize
    return format(value, "f")

@DecimalScalar.deserialize
def deserialize_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid Decimal")

@strawberry.scalar(description="ISO 8601 datetime with timezone, e.g. 2025-10-20T19:00:00+03:00")
def DateTimeTZ(value: dt.datetime) -> str:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("Datetime must be timezone-aware")
    return value.isoformat()

@DateTimeTZ.deserialize
def deserialize_datetime(value) -> dt.datetime:
    try:
        dt_obj = dt.datetime.fromisoformat(str(value))
        if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
            raise ValueError("Datetime must be timezone-aware")
        return dt_obj
    except Exception:
        raise ValueError("Invalid datetime format")
