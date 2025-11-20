import dataclasses
import json
from typing import Optional, Dict, List, Any
import strawberry

@strawberry.type
class SimplePriceEntry:
    coin_id: str
    vs_currency: str
    price: float

    market_cap: Optional[float] = None
    vol_24h: Optional[float] = None
    change_24h: Optional[float] = None
    last_updated_at: Optional[int] = None



@strawberry.type
class ListSimplePricesEntry:
    simple_prices: list[SimplePriceEntry] = strawberry.field(
        default_factory=list
    )

    def to_redis_value(self) -> str:
        return json.dumps(
            dataclasses.asdict(self),
            ensure_ascii=False,
            separators=(",", ":")
        )

    @classmethod
    def from_redis_value(cls, value: str) -> "ListSimplePricesEntry":
        data = json.loads(value)
        raw = data.get("simple_prices") or []

        items: list[SimplePriceEntry] = []
        for item in raw:
            if isinstance(item, dict):
                items.append(SimplePriceEntry(
                    coin_id=str(item.get("coin_id", "")),
                    vs_currency=str(item.get("vs_currency", "")),
                    price=float(item.get("price", 0.0)),
                    market_cap=item.get("market_cap"),
                    vol_24h=item.get("vol_24h"),
                    change_24h=item.get("change_24h"),
                    last_updated_at=item.get("last_updated_at"),
                ))

        return cls(simple_prices=items)


def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def parse_list_simple_price(raw: Dict[str, Dict[str, Any]]) -> ListSimplePricesEntry:
    """
   /simple/price -> ListSimplePricesEntry
    - парсим все монеты и все валюты
    - ts храним ТАК КАК ПРИШЁЛ (если есть) — без конверсий
    """
    if not isinstance(raw, dict):
        return ListSimplePricesEntry()

    rows: ListSimplePricesEntry = ListSimplePricesEntry()
    flag_suffixes = ("_market_cap", "_24h_vol", "_24h_change")

    for coin_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue

        # если время есть — просто приводим к int, иначе None
        ts = payload.get("last_updated_at")
        ts = int(ts) if isinstance(ts, (int, float)) else None

        # для поиска флагов без учёта регистра
        lower_map = {str(k).lower(): v for k, v in payload.items()}

        # валюты = все ключи, которые не флаги и не last_updated_at
        for k, v in payload.items():
            kl = str(k).lower()
            if kl == "last_updated_at" or any(kl.endswith(suf) for suf in flag_suffixes):
                continue

            vs_code = kl  # 'usd' / 'eur' / 'rub' / ...
            price = _to_float(v)
            if price is None:
                continue

            mc  = _to_float(lower_map.get(f"{vs_code}_market_cap"))
            vol = _to_float(lower_map.get(f"{vs_code}_24h_vol"))
            chg = _to_float(lower_map.get(f"{vs_code}_24h_change"))

            rows.simple_prices.append(SimplePriceEntry(
                coin_id=coin_id,
                vs_currency=vs_code,
                price=price,
                market_cap=mc,
                vol_24h=vol,
                change_24h=chg,
                last_updated_at=ts,
            ))
    return rows