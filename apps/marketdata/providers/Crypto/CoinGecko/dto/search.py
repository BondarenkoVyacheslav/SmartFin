from typing import List, Optional, Dict, Any
import strawberry


@strawberry.type
class SearchCoin:
    id: str
    name: str
    api_symbol: str
    symbol: str
    market_cap_rank: Optional[int] = None
    thumb: Optional[str] = None
    large: Optional[str] = None


@strawberry.type
class SearchExchange:
    id: str
    name: str
    market_type: Optional[str] = None
    thumb: Optional[str] = None
    large: Optional[str] = None


@strawberry.type
class SearchIco:
    """
    В доке по /search структура ICO довольно богатая, но для MVP берём только базовые поля.
    Остальное при желании можно будет дорасширить.
    """
    id: Optional[str] = None
    name: Optional[str] = None
    symbol: Optional[str] = None


@strawberry.type
class SearchCategory:
    id: str
    name: str


@strawberry.type
class SearchNft:
    id: str
    name: str
    symbol: str
    thumb: Optional[str] = None


@strawberry.type
class SearchResult:
    coins: List[SearchCoin]
    exchanges: List[SearchExchange]
    icos: List[SearchIco]
    categories: List[SearchCategory]
    nfts: List[SearchNft]


def parse_search_result(raw: Dict[str, Any]) -> SearchResult:
    """
    Нормализует ответ CoinGecko /search в DTO SearchResult.
    Ожидает raw в том виде, как его вернул requests/httpx/json().
    """

    coins: List[SearchCoin] = []
    for item in raw.get("coins", []) or []:
        if not isinstance(item, dict):
            continue
        coins.append(
            SearchCoin(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                api_symbol=str(item.get("api_symbol", "")),
                symbol=str(item.get("symbol", "")),
                market_cap_rank=item.get("market_cap_rank"),
                thumb=item.get("thumb"),
                large=item.get("large"),
            )
        )

    exchanges: List[SearchExchange] = []
    for item in raw.get("exchanges", []) or []:
        if not isinstance(item, dict):
            continue
        exchanges.append(
            SearchExchange(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                market_type=item.get("market_type"),
                thumb=item.get("thumb"),
                large=item.get("large"),
            )
        )

    icos: List[SearchIco] = []
    for item in raw.get("icos", []) or []:
        if not isinstance(item, dict):
            continue
        icos.append(
            SearchIco(
                id=item.get("id"),
                name=item.get("name"),
                symbol=item.get("symbol"),
            )
        )

    categories: List[SearchCategory] = []
    for item in raw.get("categories", []) or []:
        if not isinstance(item, dict):
            continue
        categories.append(
            SearchCategory(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
            )
        )

    nfts: List[SearchNft] = []
    for item in raw.get("nfts", []) or []:
        if not isinstance(item, dict):
            continue
        nfts.append(
            SearchNft(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                symbol=str(item.get("symbol", "")),
                thumb=item.get("thumb"),
            )
        )

    return SearchResult(
        coins=coins,
        exchanges=exchanges,
        icos=icos,
        categories=categories,
        nfts=nfts,
    )
