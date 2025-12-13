from typing import Optional, List, Dict, Any
import strawberry
from strawberry.scalars import JSON

from apps.marketdata.services.redis_json import RedisJSON


# ---------- Small nested DTOs ----------

@strawberry.type
class ImageSet:
    thumb: Optional[str] = None
    small: Optional[str] = None
    large: Optional[str] = None


@strawberry.type
class LinksReposUrl:
    github: List[str] = strawberry.field(default_factory=list)
    bitbucket: List[str] = strawberry.field(default_factory=list)


@strawberry.type
class Links:
    homepage: List[str] = strawberry.field(default_factory=list)
    whitepaper: Optional[str] = None
    blockchain_site: List[str] = strawberry.field(default_factory=list)
    official_forum_url: List[str] = strawberry.field(default_factory=list)
    chat_url: List[str] = strawberry.field(default_factory=list)
    announcement_url: List[str] = strawberry.field(default_factory=list)
    snapshot_url: Optional[str] = None
    twitter_screen_name: Optional[str] = None
    facebook_username: Optional[str] = None
    bitcointalk_thread_identifier: Optional[int] = None
    telegram_channel_identifier: Optional[str] = None
    subreddit_url: Optional[str] = None
    repos_url: Optional[LinksReposUrl] = None


@strawberry.type
class CodeAddDel4Weeks:
    additions: Optional[int] = None
    deletions: Optional[int] = None


@strawberry.type
class DeveloperData:
    forks: Optional[int] = None
    stars: Optional[int] = None
    subscribers: Optional[int] = None
    total_issues: Optional[int] = None
    closed_issues: Optional[int] = None
    pull_requests_merged: Optional[int] = None
    pull_request_contributors: Optional[int] = None
    code_additions_deletions_4_weeks: Optional[CodeAddDel4Weeks] = None
    commit_count_4_weeks: Optional[int] = None


@strawberry.type
class CommunityData:
    facebook_likes: Optional[int] = None
    reddit_average_posts_48h: Optional[float] = None
    reddit_average_comments_48h: Optional[float] = None
    reddit_subscribers: Optional[int] = None
    reddit_accounts_active_48h: Optional[int] = None
    telegram_channel_user_count: Optional[int] = None


@strawberry.type
class Sparkline7d:
    price: List[float] = strawberry.field(default_factory=list)


@strawberry.type(name="CoinsIdConverted3")
class Converted3:
    btc: Optional[float] = None
    eth: Optional[float] = None
    usd: Optional[float] = None


@strawberry.type(name="CoinsIdMarketRef")
class MarketRef:
    name: Optional[str] = None
    identifier: Optional[str] = None
    has_trading_incentive: Optional[bool] = None


@strawberry.type(name="ExchangeTickersTicker")
class Ticker:
    base: Optional[str] = None
    target: Optional[str] = None
    market: Optional[MarketRef] = None
    last: Optional[float] = None
    volume: Optional[float] = None
    converted_last: Optional[Converted3] = None
    converted_volume: Optional[Converted3] = None
    trust_score: Optional[str] = None
    bid_ask_spread_percentage: Optional[float] = None
    timestamp: Optional[str] = None
    last_traded_at: Optional[str] = None
    last_fetch_at: Optional[str] = None
    is_anomaly: Optional[bool] = None
    is_stale: Optional[bool] = None
    trade_url: Optional[str] = None
    token_info_url: Optional[str] = None
    coin_id: Optional[str] = None
    target_coin_id: Optional[str] = None
    coin_mcap_usd: Optional[float] = None


# ---------- MarketData (big block) ----------
# Для всех огромных карт по валютам (current_price, ath, atl, *_in_currency, ...),
# используем JSON, чтобы не городить десятки полей.

@strawberry.type
class MarketData:
    current_price: Optional[JSON] = None
    total_value_locked: Optional[float] = None
    mcap_to_tvl_ratio: Optional[float] = None
    fdv_to_tvl_ratio: Optional[float] = None
    roi: Optional[JSON] = None

    ath: Optional[JSON] = None
    ath_change_percentage: Optional[JSON] = None
    ath_date: Optional[JSON] = None

    atl: Optional[JSON] = None
    atl_change_percentage: Optional[JSON] = None
    atl_date: Optional[JSON] = None

    market_cap: Optional[JSON] = None
    market_cap_rank: Optional[int] = None
    fully_diluted_valuation: Optional[JSON] = None
    market_cap_fdv_ratio: Optional[float] = None

    total_volume: Optional[JSON] = None
    high_24h: Optional[JSON] = None
    low_24h: Optional[JSON] = None

    price_change_24h: Optional[float] = None
    price_change_percentage_24h: Optional[float] = None

    price_change_percentage_7d: Optional[float] = None
    price_change_percentage_14d: Optional[float] = None
    price_change_percentage_30d: Optional[float] = None
    price_change_percentage_60d: Optional[float] = None
    price_change_percentage_200d: Optional[float] = None
    price_change_percentage_1y: Optional[float] = None

    price_change_24h_in_currency: Optional[JSON] = None
    price_change_percentage_1h_in_currency: Optional[JSON] = None
    price_change_percentage_24h_in_currency: Optional[JSON] = None
    price_change_percentage_7d_in_currency: Optional[JSON] = None
    price_change_percentage_14d_in_currency: Optional[JSON] = None
    price_change_percentage_30d_in_currency: Optional[JSON] = None
    price_change_percentage_60d_in_currency: Optional[JSON] = None
    price_change_percentage_200d_in_currency: Optional[JSON] = None
    price_change_percentage_1y_in_currency: Optional[JSON] = None

    market_cap_change_24h: Optional[float] = None
    market_cap_change_percentage_24h: Optional[float] = None
    market_cap_change_24h_in_currency: Optional[JSON] = None
    market_cap_change_percentage_24h_in_currency: Optional[JSON] = None

    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    max_supply_infinite: Optional[bool] = None
    circulating_supply: Optional[float] = None

    sparkline_7d: Optional[Sparkline7d] = None
    last_updated: Optional[str] = None


# ---------- Root DTO ----------

@strawberry.type
class CoinDetail(RedisJSON):
    # базовая идентификация
    id: str
    symbol: str
    name: str
    web_slug: Optional[str] = None

    # платформы и контрактные адреса
    asset_platform_id: Optional[str] = None
    platforms: Optional[JSON] = None                     # Dict[str, str]
    detail_platforms: Optional[JSON] = None              # Dict[str, {decimal_place, contract_address}]

    # мета
    block_time_in_minutes: Optional[int] = None
    hashing_algorithm: Optional[str] = None
    categories: List[str] = strawberry.field(default_factory=list)
    preview_listing: Optional[bool] = None
    public_notice: Optional[str] = None
    additional_notices: List[str] = strawberry.field(default_factory=list)

    # локализация и описания (многоязычные карты)
    localization: Optional[JSON] = None                  # Dict[lang, str]
    description: Optional[JSON] = None                   # Dict[lang, str]

    # ссылки и картинки
    links: Optional[Links] = None
    image: Optional[ImageSet] = None

    # происхождение/даты
    country_origin: Optional[str] = None
    genesis_date: Optional[str] = None

    # социалка/ранги
    sentiment_votes_up_percentage: Optional[float] = None
    sentiment_votes_down_percentage: Optional[float] = None
    watchlist_portfolio_users: Optional[int] = None
    market_cap_rank: Optional[int] = None

    # рынок
    market_data: Optional[MarketData] = None

    # комьюнити/разработка
    community_data: Optional[CommunityData] = None
    developer_data: Optional[DeveloperData] = None

    # статусы, обновления
    status_updates: List[JSON] = strawberry.field(default_factory=list)
    last_updated: Optional[str] = None

    # тикеры
    tickers: List[Ticker] = strawberry.field(default_factory=list)


# ---------- Parsers (raw -> DTO) ----------

def _parse_links(raw: Dict[str, Any]) -> Links:
    repos = raw.get("repos_url") or {}
    return Links(
        homepage=raw.get("homepage") or [],
        whitepaper=raw.get("whitepaper"),
        blockchain_site=raw.get("blockchain_site") or [],
        official_forum_url=raw.get("official_forum_url") or [],
        chat_url=raw.get("chat_url") or [],
        announcement_url=raw.get("announcement_url") or [],
        snapshot_url=raw.get("snapshot_url"),
        twitter_screen_name=raw.get("twitter_screen_name"),
        facebook_username=raw.get("facebook_username"),
        bitcointalk_thread_identifier=raw.get("bitcointalk_thread_identifier"),
        telegram_channel_identifier=raw.get("telegram_channel_identifier"),
        subreddit_url=raw.get("subreddit_url"),
        repos_url=LinksReposUrl(
            github=repos.get("github") or [],
            bitbucket=repos.get("bitbucket") or [],
        ),
    )


def _parse_image(raw: Dict[str, Any]) -> ImageSet:
    return ImageSet(
        thumb=raw.get("thumb"),
        small=raw.get("small"),
        large=raw.get("large"),
    )


def _parse_dev(raw: Dict[str, Any]) -> DeveloperData:
    adddel = raw.get("code_additions_deletions_4_weeks") or {}
    return DeveloperData(
        forks=raw.get("forks"),
        stars=raw.get("stars"),
        subscribers=raw.get("subscribers"),
        total_issues=raw.get("total_issues"),
        closed_issues=raw.get("closed_issues"),
        pull_requests_merged=raw.get("pull_requests_merged"),
        pull_request_contributors=raw.get("pull_request_contributors"),
        code_additions_deletions_4_weeks=CodeAddDel4Weeks(
            additions=adddel.get("additions"),
            deletions=adddel.get("deletions"),
        ),
        commit_count_4_weeks=raw.get("commit_count_4_weeks"),
    )


def _parse_comm(raw: Dict[str, Any]) -> CommunityData:
    return CommunityData(
        facebook_likes=raw.get("facebook_likes"),
        reddit_average_posts_48h=raw.get("reddit_average_posts_48h"),
        reddit_average_comments_48h=raw.get("reddit_average_comments_48h"),
        reddit_subscribers=raw.get("reddit_subscribers"),
        reddit_accounts_active_48h=raw.get("reddit_accounts_active_48h"),
        telegram_channel_user_count=raw.get("telegram_channel_user_count"),
    )


def _parse_market_data(raw: Dict[str, Any]) -> MarketData:
    if not raw:
        return MarketData()

    spark = None
    if isinstance(raw.get("sparkline_7d"), dict):
        spark = Sparkline7d(price=raw["sparkline_7d"].get("price") or [])

    return MarketData(
        current_price=raw.get("current_price"),
        total_value_locked=raw.get("total_value_locked"),
        mcap_to_tvl_ratio=raw.get("mcap_to_tvl_ratio"),
        fdv_to_tvl_ratio=raw.get("fdv_to_tvl_ratio"),
        roi=raw.get("roi"),

        ath=raw.get("ath"),
        ath_change_percentage=raw.get("ath_change_percentage"),
        ath_date=raw.get("ath_date"),

        atl=raw.get("atl"),
        atl_change_percentage=raw.get("atl_change_percentage"),
        atl_date=raw.get("atl_date"),

        market_cap=raw.get("market_cap"),
        market_cap_rank=raw.get("market_cap_rank"),
        fully_diluted_valuation=raw.get("fully_diluted_valuation"),
        market_cap_fdv_ratio=raw.get("market_cap_fdv_ratio"),

        total_volume=raw.get("total_volume"),
        high_24h=raw.get("high_24h"),
        low_24h=raw.get("low_24h"),

        price_change_24h=raw.get("price_change_24h"),
        price_change_percentage_24h=raw.get("price_change_percentage_24h"),

        price_change_percentage_7d=raw.get("price_change_percentage_7d"),
        price_change_percentage_14d=raw.get("price_change_percentage_14d"),
        price_change_percentage_30d=raw.get("price_change_percentage_30d"),
        price_change_percentage_60d=raw.get("price_change_percentage_60d"),
        price_change_percentage_200d=raw.get("price_change_percentage_200d"),
        price_change_percentage_1y=raw.get("price_change_percentage_1y"),

        price_change_24h_in_currency=raw.get("price_change_24h_in_currency"),
        price_change_percentage_1h_in_currency=raw.get("price_change_percentage_1h_in_currency"),
        price_change_percentage_24h_in_currency=raw.get("price_change_percentage_24h_in_currency"),
        price_change_percentage_7d_in_currency=raw.get("price_change_percentage_7d_in_currency"),
        price_change_percentage_14d_in_currency=raw.get("price_change_percentage_14d_in_currency"),
        price_change_percentage_30d_in_currency=raw.get("price_change_percentage_30d_in_currency"),
        price_change_percentage_60d_in_currency=raw.get("price_change_percentage_60d_in_currency"),
        price_change_percentage_200d_in_currency=raw.get("price_change_percentage_200d_in_currency"),
        price_change_percentage_1y_in_currency=raw.get("price_change_percentage_1y_in_currency"),

        market_cap_change_24h=raw.get("market_cap_change_24h"),
        market_cap_change_percentage_24h=raw.get("market_cap_change_percentage_24h"),
        market_cap_change_24h_in_currency=raw.get("market_cap_change_24h_in_currency"),
        market_cap_change_percentage_24h_in_currency=raw.get("market_cap_change_percentage_24h_in_currency"),

        total_supply=raw.get("total_supply"),
        max_supply=raw.get("max_supply"),
        max_supply_infinite=raw.get("max_supply_infinite"),
        circulating_supply=raw.get("circulating_supply"),

        sparkline_7d=spark,
        last_updated=raw.get("last_updated"),
    )


def _parse_ticker(t: Dict[str, Any]) -> Ticker:
    market = t.get("market") or {}
    return Ticker(
        base=t.get("base"),
        target=t.get("target"),
        market=MarketRef(
            name=market.get("name"),
            identifier=market.get("identifier"),
            has_trading_incentive=market.get("has_trading_incentive"),
        ),
        last=t.get("last"),
        volume=t.get("volume"),
        converted_last=Converted3(**(t.get("converted_last") or {})),
        converted_volume=Converted3(**(t.get("converted_volume") or {})),
        trust_score=t.get("trust_score"),
        bid_ask_spread_percentage=t.get("bid_ask_spread_percentage"),
        timestamp=t.get("timestamp"),
        last_traded_at=t.get("last_traded_at"),
        last_fetch_at=t.get("last_fetch_at"),
        is_anomaly=t.get("is_anomaly"),
        is_stale=t.get("is_stale"),
        trade_url=t.get("trade_url"),
        token_info_url=t.get("token_info_url"),
        coin_id=t.get("coin_id"),
        target_coin_id=t.get("target_coin_id"),
        coin_mcap_usd=t.get("coin_mcap_usd"),
    )


def parse_coin_detail(raw: Dict[str, Any]) -> CoinDetail:
    links = _parse_links(raw.get("links") or {}) if isinstance(raw.get("links"), dict) else None
    image = _parse_image(raw.get("image") or {}) if isinstance(raw.get("image"), dict) else None
    community = _parse_comm(raw.get("community_data") or {}) if isinstance(raw.get("community_data"), dict) else None
    developer = _parse_dev(raw.get("developer_data") or {}) if isinstance(raw.get("developer_data"), dict) else None
    market_data = _parse_market_data(raw.get("market_data") or {}) if isinstance(raw.get("market_data"), dict) else None

    tickers_raw = raw.get("tickers") or []
    tickers = [_parse_ticker(t) for t in tickers_raw if isinstance(t, dict)]

    return CoinDetail(
        id=raw.get("id", ""),
        symbol=raw.get("symbol", ""),
        name=raw.get("name", ""),
        web_slug=raw.get("web_slug"),

        asset_platform_id=raw.get("asset_platform_id"),
        platforms=raw.get("platforms"),
        detail_platforms=raw.get("detail_platforms"),

        block_time_in_minutes=raw.get("block_time_in_minutes"),
        hashing_algorithm=raw.get("hashing_algorithm"),
        categories=raw.get("categories") or [],
        preview_listing=raw.get("preview_listing"),
        public_notice=raw.get("public_notice"),
        additional_notices=raw.get("additional_notices") or [],

        localization=raw.get("localization"),
        description=raw.get("description"),

        links=links,
        image=image,

        country_origin=raw.get("country_origin"),
        genesis_date=raw.get("genesis_date"),

        sentiment_votes_up_percentage=raw.get("sentiment_votes_up_percentage"),
        sentiment_votes_down_percentage=raw.get("sentiment_votes_down_percentage"),
        watchlist_portfolio_users=raw.get("watchlist_portfolio_users"),
        market_cap_rank=raw.get("market_cap_rank"),

        market_data=market_data,
        community_data=community,
        developer_data=developer,

        status_updates=raw.get("status_updates") or [],
        last_updated=raw.get("last_updated"),

        tickers=tickers,
    )
