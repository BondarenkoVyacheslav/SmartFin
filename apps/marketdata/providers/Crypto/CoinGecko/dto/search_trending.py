from typing import Dict, List, Optional, Any
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


# --- Общие вложенные структуры ---


@strawberry.type
class TrendingContent:
    title: Optional[str] = None
    description: Optional[str] = None


@strawberry.type
class PriceChangePercentage24hEntry:
    """Изменение цены за 24 часа в % для конкретной валюты."""
    vs_currency: str
    percentage: float


@strawberry.type
class MarketCapChangePercentage24hEntry:
    """Изменение market cap за 24 часа в % для конкретной валюты."""
    vs_currency: str
    percentage: float


@strawberry.type
class TrendingCoinData:
    price: Optional[float] = None
    price_btc: Optional[str] = None
    # словарь "валюта -> % изменения за 24ч"
    price_change_percentage_24h: Optional[List[PriceChangePercentage24hEntry]] = None
    market_cap: Optional[str] = None
    market_cap_btc: Optional[str] = None
    total_volume: Optional[str] = None
    total_volume_btc: Optional[str] = None
    sparkline: Optional[str] = None
    content: Optional[TrendingContent] = None


@strawberry.type
class TrendingCoinItem:
    id: str
    coin_id: Optional[int] = None
    name: str
    symbol: str
    market_cap_rank: Optional[int] = None
    thumb: Optional[str] = None
    small: Optional[str] = None
    large: Optional[str] = None
    slug: Optional[str] = None
    price_btc: Optional[float] = None
    score: Optional[int] = None
    data: Optional[TrendingCoinData] = None


@strawberry.type
class TrendingCoin:
    """
    Один элемент из массива "coins" в /search/trending:
    {"item": {...}}
    """
    item: TrendingCoinItem


# --- NFT-блок ---


@strawberry.type
class TrendingNftData:
    floor_price: Optional[str] = None
    floor_price_in_usd_24h_percentage_change: Optional[str] = None
    h24_volume: Optional[str] = None
    h24_average_sale_price: Optional[str] = None
    sparkline: Optional[str] = None
    content: Optional[TrendingContent] = None


@strawberry.type
class TrendingNft:
    id: str
    name: str
    symbol: str
    thumb: Optional[str] = None
    nft_contract_id: Optional[int] = None
    native_currency_symbol: Optional[str] = None
    floor_price_in_native_currency: Optional[float] = None
    floor_price_24h_percentage_change: Optional[float] = None
    data: Optional[TrendingNftData] = None


# --- Категории ---


@strawberry.type
class TrendingCategoryData:
    market_cap: Optional[float] = None
    market_cap_btc: Optional[float] = None
    total_volume: Optional[float] = None
    total_volume_btc: Optional[float] = None
    market_cap_change_percentage_24h: Optional[list[MarketCapChangePercentage24hEntry]] = None
    sparkline: Optional[str] = None


@strawberry.type
class TrendingCategory:
    id: int
    name: str
    market_cap_1h_change: Optional[float] = None
    slug: Optional[str] = None
    # в ответе приходит как строка ("84", "298", ...)
    coins_count: Optional[str] = None
    data: Optional[TrendingCategoryData] = None


# --- Корневой DTO ---


@strawberry.type
class SearchTrendingResult(RedisJSON):
    coins: List[TrendingCoin]
    nfts: List[TrendingNft]
    categories: List[TrendingCategory]


def _parse_float_mapping(raw_map: Any) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not isinstance(raw_map, dict):
        return result

    for k, v in raw_map.items():
        try:
            if isinstance(v, (int, float)):
                result[str(k)] = float(v)
            elif isinstance(v, str):
                result[str(k)] = float(v)
        except (ValueError, TypeError):
            # просто скипаем кривые значения
            continue
    return result

def _parse_price_change_percentage_entries(
    raw: Any,
) -> Optional[List[PriceChangePercentage24hEntry]]:
    """
    Превращаем dict вида {"usd": -4.04, "eur": -3.9, ...}
    в список DTO PriceChangePercentage24hEntry.
    """
    if not isinstance(raw, dict):
        return None

    result: List[PriceChangePercentage24hEntry] = []

    for code, value in raw.items():
        try:
            # value может быть числом или строкой — приводим к float
            percentage = float(value)
        except (TypeError, ValueError):
            continue

        result.append(
            PriceChangePercentage24hEntry(
                vs_currency=str(code),
                percentage=percentage,
            )
        )

    return result or None


def _parse_market_cap_change_percentage_entries(
    raw: Any,
) -> Optional[List[MarketCapChangePercentage24hEntry]]:
    """
    Превращаем dict вида {"usd": 14.22, "eur": 13.9, ...}
    в список DTO MarketCapChangePercentage24hEntry.
    """
    if not isinstance(raw, dict):
        return None

    result: List[MarketCapChangePercentage24hEntry] = []

    for code, value in raw.items():
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            continue

        result.append(
            MarketCapChangePercentage24hEntry(
                vs_currency=str(code),
                percentage=percentage,
            )
        )

    return result or None



def parse_search_trending(raw: Dict[str, Any]) -> SearchTrendingResult:
    # --- coins ---
    coins: List[TrendingCoin] = []
    for coin_wrapper in raw.get("coins", []) or []:
        if not isinstance(coin_wrapper, dict):
            continue

        item = coin_wrapper.get("item")
        if not isinstance(item, dict):
            continue

        # data внутри item
        data_obj: Optional[TrendingCoinData] = None
        data_raw = item.get("data")
        if isinstance(data_raw, dict):
            content_raw = data_raw.get("content")
            content_obj: Optional[TrendingContent] = None
            if isinstance(content_raw, dict):
                content_obj = TrendingContent(
                    title=content_raw.get("title"),
                    description=content_raw.get("description"),
                )

            price_change_entries = _parse_price_change_percentage_entries(
                data_raw.get("price_change_percentage_24h")
            )

            data_obj = TrendingCoinData(
                price=data_raw.get("price"),
                price_btc=data_raw.get("price_btc"),
                price_change_percentage_24h=price_change_entries,
                market_cap=data_raw.get("market_cap"),
                market_cap_btc=data_raw.get("market_cap_btc"),
                total_volume=data_raw.get("total_volume"),
                total_volume_btc=data_raw.get("total_volume_btc"),
                sparkline=data_raw.get("sparkline"),
                content=content_obj,
            )

        coins.append(
            TrendingCoin(
                item=TrendingCoinItem(
                    id=str(item.get("id", "")),
                    coin_id=item.get("coin_id"),
                    name=str(item.get("name", "")),
                    symbol=str(item.get("symbol", "")),
                    market_cap_rank=item.get("market_cap_rank"),
                    thumb=item.get("thumb"),
                    small=item.get("small"),
                    large=item.get("large"),
                    slug=item.get("slug"),
                    price_btc=item.get("price_btc"),
                    score=item.get("score"),
                    data=data_obj,
                )
            )
        )

    # --- nfts ---
    nfts: List[TrendingNft] = []
    for nft_raw in raw.get("nfts", []) or []:
        if not isinstance(nft_raw, dict):
            continue

        nft_data_raw = nft_raw.get("data")
        nft_data_obj: Optional[TrendingNftData] = None
        if isinstance(nft_data_raw, dict):
            content_raw = nft_data_raw.get("content")
            content_obj: Optional[TrendingContent] = None
            if isinstance(content_raw, dict):
                content_obj = TrendingContent(
                    title=content_raw.get("title"),
                    description=content_raw.get("description"),
                )

            nft_data_obj = TrendingNftData(
                floor_price=nft_data_raw.get("floor_price"),
                floor_price_in_usd_24h_percentage_change=nft_data_raw.get(
                    "floor_price_in_usd_24h_percentage_change"
                ),
                h24_volume=nft_data_raw.get("h24_volume"),
                h24_average_sale_price=nft_data_raw.get("h24_average_sale_price"),
                sparkline=nft_data_raw.get("sparkline"),
                content=content_obj,
            )

        nfts.append(
            TrendingNft(
                id=str(nft_raw.get("id", "")),
                name=str(nft_raw.get("name", "")),
                symbol=str(nft_raw.get("symbol", "")),
                thumb=nft_raw.get("thumb"),
                nft_contract_id=nft_raw.get("nft_contract_id"),
                native_currency_symbol=nft_raw.get("native_currency_symbol"),
                floor_price_in_native_currency=nft_raw.get(
                    "floor_price_in_native_currency"
                ),
                floor_price_24h_percentage_change=nft_raw.get(
                    "floor_price_24h_percentage_change"
                ),
                data=nft_data_obj,
            )
        )

    # --- categories ---
    categories: List[TrendingCategory] = []
    for cat_raw in raw.get("categories", []) or []:
        if not isinstance(cat_raw, dict):
            continue

        cat_data_raw = cat_raw.get("data")
        cat_data_obj: Optional[TrendingCategoryData] = None
        if isinstance(cat_data_raw, dict):
            mc_change_entries = _parse_market_cap_change_percentage_entries(
                cat_data_raw.get("market_cap_change_percentage_24h")
            )
            cat_data_obj = TrendingCategoryData(
                market_cap=cat_data_raw.get("market_cap"),
                market_cap_btc=cat_data_raw.get("market_cap_btc"),
                total_volume=cat_data_raw.get("total_volume"),
                total_volume_btc=cat_data_raw.get("total_volume_btc"),
                market_cap_change_percentage_24h=mc_change_entries,
                sparkline=cat_data_raw.get("sparkline"),
            )

        categories.append(
            TrendingCategory(
                id=int(cat_raw.get("id", 0)),
                name=str(cat_raw.get("name", "")),
                market_cap_1h_change=cat_raw.get("market_cap_1h_change"),
                slug=cat_raw.get("slug"),
                coins_count=str(cat_raw.get("coins_count")) if cat_raw.get("coins_count") is not None else None,
                data=cat_data_obj,
            )
        )

    return SearchTrendingResult(
        coins=coins,
        nfts=nfts,
        categories=categories,
    )
