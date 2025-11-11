from typing import Optional, Dict, Union
import strawberry

@strawberry.type
class Ping:
    gecko_says: Optional[str] = None


async def parser_ping(
    raw: Dict[str, Union[str, Dict[str, str]]]
) -> Optional[Ping]:
    pass