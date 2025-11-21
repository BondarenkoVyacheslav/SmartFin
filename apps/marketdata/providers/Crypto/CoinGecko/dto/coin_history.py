import json
from typing import Any, Dict, Optional
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.dto.redis_json import RedisJSON


@strawberry.type
class ImageDTO:
    thumb: Optional[str] = None
    small: Optional[str] = None


@strawberry.type
class MarketDataDTO:
    # словари вида {"usd": 42074.70, "eur": 38057.70, ...}
    current_price: Optional[Dict[str, float]] = None
    market_cap: Optional[Dict[str, float]] = None
    total_volume: Optional[Dict[str, float]] = None


@strawberry.type
class CommunityDataDTO:
    facebook_likes: Optional[int] = None
    reddit_average_posts_48h: Optional[float] = None
    reddit_average_comments_48h: Optional[float] = None
    reddit_subscribers: Optional[int] = None
    reddit_accounts_active_48h: Optional[float] = None


@strawberry.type
class CodeAddDel4WeeksDTO:
    additions: Optional[int] = None
    deletions: Optional[int] = None


@strawberry.type
class DeveloperDataDTO:
    forks: Optional[int] = None
    stars: Optional[int] = None
    subscribers: Optional[int] = None
    total_issues: Optional[int] = None
    closed_issues: Optional[int] = None
    pull_requests_merged: Optional[int] = None
    pull_request_contributors: Optional[int] = None
    code_additions_deletions_4_weeks: Optional[CodeAddDel4WeeksDTO] = None
    commit_count_4_weeks: Optional[int] = None


@strawberry.type
class PublicInterestStatsDTO:
    alexa_rank: Optional[int] = None
    bing_matches: Optional[int] = None


@strawberry.type
class HistoryMeta:
    # эхо параметров — удобно фронту/кэшу
    coin_id: str
    date: str
    localization: bool


@strawberry.type
class CoinHistory(RedisJSON):
    id: Optional[str] = None
    symbol: Optional[str] = None
    name: Optional[str] = None

    # если localization=true — вернётся словарь локализаций имени
    localization: Optional[Dict[str, str]] = None

    image: Optional[ImageDTO] = None
    market_data: Optional[MarketDataDTO] = None
    community_data: Optional[CommunityDataDTO] = None
    developer_data: Optional[DeveloperDataDTO] = None
    public_interest_stats: Optional[PublicInterestStatsDTO] = None

    # наше поле (не от API)
    meta: Optional[HistoryMeta] = None

    @classmethod
    def from_redis_value(cls, value: str) -> "CoinHistory":
        data = json.loads(value)

        return parse_coin_history(data)


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        # CoinGecko иногда отдаёт числа как float с .0 — приведём аккуратно
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _to_currency_map(raw: Any) -> Optional[Dict[str, float]]:
    if not isinstance(raw, dict):
        return None
    out: Dict[str, float] = {}
    for k, v in raw.items():
        fv = _to_float(v)
        if fv is not None:
            out[str(k).lower()] = fv  # ключи нормализуем в lower
    return out or None


def _to_str_map(raw: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(v, str):
            out[str(k)] = v
    return out or None


def _parse_image(raw: Any) -> Optional[ImageDTO]:
    if not isinstance(raw, dict):
        return None
    return ImageDTO(
        thumb=raw.get("thumb"),
        small=raw.get("small"),
    )


def _parse_market_data(raw: Any) -> Optional[MarketDataDTO]:
    if not isinstance(raw, dict):
        return None
    return MarketDataDTO(
        current_price=_to_currency_map(raw.get("current_price")),
        market_cap=_to_currency_map(raw.get("market_cap")),
        total_volume=_to_currency_map(raw.get("total_volume")),
    )


def _parse_community(raw: Any) -> Optional[CommunityDataDTO]:
    if not isinstance(raw, dict):
        return None
    return CommunityDataDTO(
        facebook_likes=_to_int(raw.get("facebook_likes")),
        reddit_average_posts_48h=_to_float(raw.get("reddit_average_posts_48h")),
        reddit_average_comments_48h=_to_float(raw.get("reddit_average_comments_48h")),
        reddit_subscribers=_to_int(raw.get("reddit_subscribers")),
        reddit_accounts_active_48h=_to_float(raw.get("reddit_accounts_active_48h")),
    )


def _parse_code_add_del(raw: Any) -> Optional[CodeAddDel4WeeksDTO]:
    if not isinstance(raw, dict):
        return None
    return CodeAddDel4WeeksDTO(
        additions=_to_int(raw.get("additions")),
        deletions=_to_int(raw.get("deletions")),
    )


def _parse_developer(raw: Any) -> Optional[DeveloperDataDTO]:
    if not isinstance(raw, dict):
        return None
    return DeveloperDataDTO(
        forks=_to_int(raw.get("forks")),
        stars=_to_int(raw.get("stars")),
        subscribers=_to_int(raw.get("subscribers")),
        total_issues=_to_int(raw.get("total_issues")),
        closed_issues=_to_int(raw.get("closed_issues")),
        pull_requests_merged=_to_int(raw.get("pull_requests_merged")),
        pull_request_contributors=_to_int(raw.get("pull_request_contributors")),
        code_additions_deletions_4_weeks=_parse_code_add_del(
            raw.get("code_additions_deletions_4_weeks")
        ),
        commit_count_4_weeks=_to_int(raw.get("commit_count_4_weeks")),
    )


def _parse_public_interest(raw: Any) -> Optional[PublicInterestStatsDTO]:
    if not isinstance(raw, dict):
        return None
    return PublicInterestStatsDTO(
        alexa_rank=_to_int(raw.get("alexa_rank")),
        bing_matches=_to_int(raw.get("bing_matches")),
    )


def parse_coin_history(
        raw: Dict[str, Any],
) -> CoinHistory:
    return CoinHistory(
        id=raw.get("id"),
        symbol=raw.get("symbol"),
        name=raw.get("name"),
        localization=_to_str_map(raw.get("localization")),
        image=_parse_image(raw.get("image")),
        market_data=_parse_market_data(raw.get("market_data")),
        community_data=_parse_community(raw.get("community_data")),
        developer_data=_parse_developer(raw.get("developer_data")),
        public_interest_stats=_parse_public_interest(raw.get("public_interest_stats")),
    )
