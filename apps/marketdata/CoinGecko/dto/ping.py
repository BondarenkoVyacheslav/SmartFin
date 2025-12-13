from typing import Optional, Dict, Union
import strawberry


@strawberry.type
class Ping:
    gecko_says: Optional[str] = None


async def parser_ping(
        raw: Dict[str, Union[str, Dict[str, str]]]
) -> Optional[Ping]:
    """
    Нормализует ответ CoinGecko /ping в DTO Ping.

    Поддерживаемые формы:
      - {"gecko_says": "..."}
      - {"status": {"gecko_says": "..."}}

    Возвращает:
      - Ping(...) — если удалось извлечь gecko_says
      - None — если структура не соответствует ожиданиям
    """
    if not isinstance(raw, dict):
        return None

    gecko_says: Optional[str] = None

    # Прямая форма
    if "gecko_says" in raw and isinstance(raw["gecko_says"], str):
        gecko_says = raw["gecko_says"]
    else:
        # Вложенная форма через "status"
        status = raw.get("status")
        if isinstance(status, dict):
            val = status.get("gecko_says")
            if isinstance(val, str):
                gecko_says = val

    if gecko_says is None:
        return None

    return Ping(gecko_says=gecko_says)
