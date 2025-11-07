from apps.marketdata.domains.domain import Domain

from typing import (
    Iterable, Sequence, List, Optional, Dict, Any, Literal
)
from datetime import date, datetime
from apps.marketdata.providers.provider import Quote, Candle


class StockMarketUSA(Domain):
    """Бумаги США: котировки/свечи/профили/финансы/корпдействия/календарь/деривативы."""
    def get_quotes(self, symbols: Sequence[str]) -> List[Quote]:
        # TODO
        return []

    def get_candles(self, symbol: str, interval: str,
                    since: Optional[date] = None, till: Optional[date] = None) -> List[Candle]:
        # TODO
        return []

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        # TODO
        return {}

    def get_financials(self, symbol: str,
                        statement: Literal["income", "balance", "cashflow"] = "income",
                        period: Literal["annual", "quarter"] = "annual") -> List[Dict[str, Any]]:
        # TODO
        return []

    def get_corporate_actions(self, symbol: str,
                              types: Optional[Sequence[Literal["dividend", "split", "rights", "merger"]]] = None,
                              since: Optional[date] = None, till: Optional[date] = None) -> List[Dict[str, Any]]:
        # TODO
        return []

    def get_dividends(self, symbol: str,
                      since: Optional[date] = None, till: Optional[date] = None) -> List[Dict[str, Any]]:
        # TODO
        return []

    def get_splits(self, symbol: str,
                   since: Optional[date] = None, till: Optional[date] = None) -> List[Dict[str, Any]]:
        # TODO
        return []

    def get_earnings_calendar(self, symbol: Optional[str] = None,
                              date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[Dict[str, Any]]:
        # TODO
        return []

    def get_options_chain(self, underlying: str, expiry: Optional[date] = None) -> Dict[str, Any]:
        # TODO
        return {}

    def get_futures_chain(self, underlying: str) -> Dict[str, Any]:
        # TODO
        return {}

    # Референс/мета, связанные с рынками США
    def list_exchanges(self, country: Optional[str] = None) -> List[Dict[str, Any]]:
        # TODO
        return []

    def trading_sessions(self, exchange_code: str, on_date: Optional[date] = None) -> Dict[str, Any]:
        # TODO
        return {}

    def market_holidays(self, country_code: str, year: Optional[int] = None) -> List[date]:
        # TODO
        return []

    def market_status(self, exchange_code: Optional[str] = None) -> Dict[str, Any]:
        # TODO
        return {}

    def search_symbols(self, query: str, exchange: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        # TODO
        return []