from __future__ import annotations

from typing import Protocol

from exchange_portfolio_models import ExchangeCredentials, PortfolioState


# -----------------------------
# Интерфейс адаптера биржи
# -----------------------------

class ExchangeAdapter(Protocol):
    async def fetch_portfolio_state(self, creds: ExchangeCredentials) -> PortfolioState:
        ...
