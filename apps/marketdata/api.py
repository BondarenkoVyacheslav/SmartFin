from __future__ import annotations

from typing import (
    Iterable, Sequence, List, Optional, Dict, Any, Literal
)
from datetime import date, datetime

from django.conf import settings

from apps.marketdata.domains.crypto import Crypto
from apps.marketdata.domains.currency import Currency
from apps.marketdata.domains.products import Products
from apps.marketdata.domains.stockmarketRussia import StockMarketRussia
from apps.marketdata.domains.stockmarketUSA import StockMarketUSA
# Эти импорты у тебя уже есть в проекте — провайдерный реестр и модели DTO
from apps.marketdata.providers.registry import get_provider
from apps.marketdata.providers.provider import Quote, Candle
from apps.marketdata.services.redis_cache import RedisCacheService

class MarketDataAPI:
    """
    Фасад и маршрутизатор. НЕ работает с кэшем и провайдерами напрямую.
    Доменная логика/кэш внутри:
      - self.crypto
      - self.currency
      - self.products
      - self.stock_us
      - self.stock_ru
    """

    def __init__(self, redis_url: Optional[str] = None):
        redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        shared_cache = RedisCacheService(redis_url=redis_url, default_ttl=60)

        # Инициализация доменов
        self.crypto = Crypto(cache=shared_cache)
        self.currency = Currency(cache=shared_cache)
        self.products = Products(cache=shared_cache)
        self.stock_us = StockMarketUSA(cache=shared_cache)
        self.stock_ru = StockMarketRussia(cache=shared_cache)

    # ========= HEALTH / STATS =========

    def health(self) -> Dict[str, Any]:
        """Минимальная проверка доступности (по кэшу)."""
        # фасад ничего не знает о кэше — спросим у любого домена
        return {"redis": "ok"}  # можно расширить доменными health-check'ами

    def provider_health(self, provider_code: str) -> Dict[str, Any]:
        """Проброс в провайдера (через любой домен, где реализуешь)."""
        # TODO: решить, где хранить health провайдеров: обычно удобно в отдельном домене Meta
        return {"status": "todo", "provider": provider_code}

    # ========= QUOTES / CANDLES / ORDERBOOK / TRADES =========

    def get_quotes(self, symbols: Iterable[str], asset_class: Literal["crypto", "stock-us", "stock-ru", "fx", "products"]) -> List[Quote]:
        symbols = list(symbols)
        if asset_class == "crypto":
            return self.crypto.get_quotes(symbols)
        if asset_class == "stock-us":
            return self.stock_us.get_quotes(symbols)
        if asset_class == "stock-ru":
            return self.stock_ru.get_quotes(symbols)
        if asset_class == "fx":
            # для FX котировок фронту чаще нужны курсы, но оставим и quotes (если будут FX-тикеры у провайдеров)
            return []  # опционально: self.currency.get_quotes(symbols)
        if asset_class == "products":
            return self.products.get_quotes(symbols)
        return []

    def get_candles(self, symbol: str, interval: str,
                    asset_class: Literal["crypto", "stock-us", "stock-ru", "products"],
                    since: Optional[date] = None, till: Optional[date] = None) -> List[Candle]:
        if asset_class == "crypto":
            return self.crypto.get_candles(symbol, interval, since, till)
        if asset_class == "stock-us":
            return self.stock_us.get_candles(symbol, interval, since, till)
        if asset_class == "stock-ru":
            return self.stock_ru.get_candles(symbol, interval, since, till)
        if asset_class == "products":
            return self.products.get_candles(symbol, interval, since, till)
        return []

    def get_orderbook(self, symbol: str, asset_class: Literal["crypto", "stock-us", "stock-ru"],
                      depth: int = 20, level: Literal[1, 2] = 2) -> Dict[str, Any]:
        if asset_class == "crypto":
            return self.crypto.get_orderbook(symbol, depth, level)
        if asset_class == "stock-us":
            # TODO: реализовать стакан у домена США при наличии провайдеров
            return {}
        if asset_class == "stock-ru":
            # TODO: реализовать стакан у домена РФ (MOEX)
            return {}
        return {}

    def get_trades(self, symbol: str, asset_class: Literal["crypto", "stock-us", "stock-ru"],
                   limit: int = 100, since: Optional[datetime] = None, till: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if asset_class == "crypto":
            return self.crypto.get_trades(symbol, limit, since, till)
        if asset_class == "stock-us":
            # TODO: при наличии провайдера ленты сделок
            return []
        if asset_class == "stock-ru":
            # TODO: MOEX prints при наличии
            return []
        return []

    # ========= FX / MACRO =========

    def get_fx_rates(self, pairs: Sequence[str], source: Optional[str] = None) -> Dict[str, float]:
        return self.currency.get_fx_rates(pairs, source)

    def get_policy_rates(self, countries: Sequence[str],
                         on_date: Optional[date] = None, source: Optional[str] = None) -> Dict[str, float]:
        return self.currency.get_policy_rates(countries, on_date, source)

    # ========= CRYPTO EXTRA =========

    def get_crypto_funding_rate(self, symbol: str) -> Optional[float]:
        return self.crypto.get_funding_rate(symbol)

    def get_crypto_open_interest(self, symbol: str) -> Optional[float]:
        return self.crypto.get_open_interest(symbol)

    def get_crypto_liquidations(self, symbol: Optional[str] = None,
                                since: Optional[datetime] = None, till: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return self.crypto.get_liquidations(symbol, since, till)

    # ========= FUNDAMENTALS / CORP ACTIONS =========

    def get_company_profile(self, symbol: str, market: Literal["us", "ru"] = "us") -> Dict[str, Any]:
        return self.stock_us.get_company_profile(symbol) if market == "us" else self.stock_ru.get_company_profile(symbol)

    def get_financials(self, symbol: str, statement: Literal["income", "balance", "cashflow"] = "income",
                       period: Literal["annual", "quarter"] = "annual",
                       market: Literal["us", "ru"] = "us") -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_financials(symbol, statement, period)

    def get_corporate_actions(self, symbol: str,
                              types: Optional[Sequence[Literal["dividend", "split", "rights", "merger"]]] = None,
                              since: Optional[date] = None, till: Optional[date] = None,
                              market: Literal["us", "ru"] = "us") -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_corporate_actions(symbol, types, since, till)

    def get_dividends(self, symbol: str, since: Optional[date] = None, till: Optional[date] = None,
                      market: Literal["us", "ru"] = "us") -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_dividends(symbol, since, till)

    def get_splits(self, symbol: str, since: Optional[date] = None, till: Optional[date] = None,
                   market: Literal["us", "ru"] = "us") -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_splits(symbol, since, till)

    def get_earnings_calendar(self, symbol: Optional[str] = None,
                              date_from: Optional[date] = None, date_to: Optional[date] = None,
                              market: Literal["us", "ru"] = "us") -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_earnings_calendar(symbol, date_from, date_to)

    # ========= DERIVATIVES =========

    def get_options_chain(self, underlying: str, expiry: Optional[date] = None,
                          market: Literal["us", "ru"] = "us") -> Dict[str, Any]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_options_chain(underlying, expiry)

    def get_futures_chain(self, underlying: str,
                          market: Literal["us", "ru", "crypto"] = "us") -> Dict[str, Any]:
        if market == "crypto":
            # TODO: реализовать цепочки фьючей для крипты в Crypto (если потребуется)
            return {}
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.get_futures_chain(underlying)

    # ========= REFERENCE / SEARCH / SESSIONS =========

    def list_exchanges(self, market: Literal["us", "ru"] = "us", country: Optional[str] = None) -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.list_exchanges(country)

    def trading_sessions(self, market: Literal["us", "ru"] = "us",
                         exchange_code: str = "", on_date: Optional[date] = None) -> Dict[str, Any]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.trading_sessions(exchange_code, on_date)

    def market_holidays(self, market: Literal["us", "ru"] = "us",
                        country_code: str = "", year: Optional[int] = None) -> List[date]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.market_holidays(country_code, year)

    def market_status(self, market: Literal["us", "ru"] = "us",
                      exchange_code: Optional[str] = None) -> Dict[str, Any]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.market_status(exchange_code)

    def search_symbols(self, query: str, market: Literal["us", "ru"] = "us",
                       exchange: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        domain = self.stock_us if market == "us" else self.stock_ru
        return domain.search_symbols(query, exchange, limit)

    # ========= SUBSCRIPTIONS (schema only; возвращаем параметры канала) =========

    def subscribe_quotes(self, symbols: Sequence[str], asset_class: Literal["crypto", "stock-us", "stock-ru", "products"],
                         transport: Literal["ws", "grpc", "rest"] = "ws") -> Dict[str, Any]:
        # TODO: домены могут вернуть описание канала: topic/endpoint/token
        return {"status": "todo", "asset_class": asset_class, "transport": transport}

    def subscribe_orderbook(self, symbol: str, asset_class: Literal["crypto", "stock-us", "stock-ru"],
                            level: Literal[1, 2] = 2, transport: Literal["ws", "grpc", "rest"] = "ws") -> Dict[str, Any]:
        # TODO: домены могут вернуть описание канала
        return {"status": "todo", "asset_class": asset_class, "transport": transport, "level": level}
