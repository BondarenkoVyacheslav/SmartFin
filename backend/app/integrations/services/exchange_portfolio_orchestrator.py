from __future__ import annotations

import asyncio
from typing import List, Optional

from exchange_portfolio_ccxt_adapter import CcxtAdapter
from exchange_portfolio_models import (
    ExchangeCredentials,
    ExchangeFetchError,
    PortfolioFetchResult,
    PortfolioState,
)
from exchange_portfolio_protocols import ExchangeAdapter


# -----------------------------
# ОДИН основной класс-оркестратор
# -----------------------------

class ExchangePortfolioCollector:
    """
    Оркестратор: берёт список интеграций пользователя и параллельно
    запрашивает состояние по каждой бирже.

    Это ровно тот “один класс”, который ты можешь дергать из:
    - GraphQL resolver
    - Celery task / dramatiq / rq
    - gRPC handler в микросервисе
    """

    def __init__(
        self,
        *,
        adapter: Optional[ExchangeAdapter] = None,
        max_concurrency: int = 3,
        per_exchange_timeout_s: int = 20,
    ) -> None:
        self._adapter = adapter or CcxtAdapter()
        self._sem = asyncio.Semaphore(max_concurrency)
        self._timeout_s = per_exchange_timeout_s

    async def fetch_all(self, creds_list: List[ExchangeCredentials]) -> PortfolioFetchResult:
        tasks = [self._fetch_one(creds) for creds in creds_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        states: List[PortfolioState] = []
        errors: List[ExchangeFetchError] = []

        for creds, r in zip(creds_list, results):
            if isinstance(r, PortfolioState):
                states.append(r)
                continue

            if isinstance(r, ExchangeFetchError):
                errors.append(r)
                continue

            if isinstance(r, Exception):
                errors.append(
                    ExchangeFetchError(
                        exchange=creds.exchange,
                        error_type=type(r).__name__,
                        message=str(r),
                    )
                )
                continue

            errors.append(
                ExchangeFetchError(
                    exchange=creds.exchange,
                    error_type="UnknownResult",
                    message=f"Unexpected result type: {type(r).__name__}",
                )
            )

        return PortfolioFetchResult(states=states, errors=errors)

    async def _fetch_one(self, creds: ExchangeCredentials) -> PortfolioState | ExchangeFetchError:
        async with self._sem:
            try:
                return await asyncio.wait_for(
                    self._adapter.fetch_portfolio_state(creds),
                    timeout=self._timeout_s,
                )
            except Exception as e:
                return ExchangeFetchError(
                    exchange=creds.exchange,
                    error_type=type(e).__name__,
                    message=str(e),
                )
