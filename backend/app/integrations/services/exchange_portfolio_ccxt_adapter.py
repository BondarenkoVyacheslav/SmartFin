from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from exchange_portfolio_models import (
    BalanceLine,
    ExchangeCredentials,
    PortfolioState,
    PositionLine,
)
from exchange_portfolio_utils import _safe_trim, _to_float_or_none, _to_str_or_none


# -----------------------------
# CCXT-адаптер (рекомендуемый MVP)
# -----------------------------

class CcxtAdapter:
    """
    Требует: pip install ccxt
    Использует: ccxt.async_support

    Поддерживает:
    - balances через fetch_balance()
    - positions через fetch_positions() (если биржа поддерживает)
    """

    def __init__(self, *, request_timeout_ms: int = 12_000) -> None:
        self._timeout_ms = request_timeout_ms

    async def fetch_portfolio_state(self, creds: ExchangeCredentials) -> PortfolioState:
        try:
            import ccxt.async_support as ccxt  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "ccxt не установлен. Установи: pip install ccxt"
            ) from e

        exchange_id = creds.exchange.lower().strip()

        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"ccxt: неизвестная биржа '{exchange_id}'")

        ex_class = getattr(ccxt, exchange_id)

        params: Dict[str, Any] = {
            "apiKey": creds.api_key,
            "secret": creds.api_secret,
            "enableRateLimit": True,
            "timeout": self._timeout_ms,
        }

        # OKX / некоторые другие требуют passphrase
        if creds.passphrase:
            params["password"] = creds.passphrase

        # В ccxt "subaccount" обычно идёт как exchange-specific params,
        # поэтому оставим как пример (не включаем автоматически).
        exchange = ex_class(params)

        try:
            fetched_at = datetime.now(timezone.utc)

            # --- Балансы ---
            bal_raw = await exchange.fetch_balance()
            balances: List[BalanceLine] = []

            # ccxt баланс: dict с полями total/free/used
            free_map = (bal_raw.get("free") or {}) if isinstance(bal_raw, dict) else {}
            used_map = (bal_raw.get("used") or {}) if isinstance(bal_raw, dict) else {}
            total_map = (bal_raw.get("total") or {}) if isinstance(bal_raw, dict) else {}

            assets = set()
            if isinstance(free_map, dict):
                assets |= set(free_map.keys())
            if isinstance(used_map, dict):
                assets |= set(used_map.keys())
            if isinstance(total_map, dict):
                assets |= set(total_map.keys())

            for a in sorted(assets):
                balances.append(
                    BalanceLine(
                        asset=str(a),
                        free=_to_float_or_none(free_map.get(a)),
                        used=_to_float_or_none(used_map.get(a)),
                        total=_to_float_or_none(total_map.get(a)),
                    )
                )

            # --- Позиции (если поддерживаются) ---
            positions: List[PositionLine] = []
            has_map = getattr(exchange, "has", {}) or {}

            if isinstance(has_map, dict) and has_map.get("fetchPositions"):
                try:
                    pos_raw = await exchange.fetch_positions()
                    if isinstance(pos_raw, list):
                        for p in pos_raw:
                            if not isinstance(p, dict):
                                continue
                            positions.append(
                                PositionLine(
                                    symbol=str(p.get("symbol") or ""),
                                    side=_to_str_or_none(p.get("side")),
                                    contracts=_to_float_or_none(p.get("contracts") or p.get("contractSize")),
                                    entry_price=_to_float_or_none(p.get("entryPrice")),
                                    mark_price=_to_float_or_none(p.get("markPrice")),
                                    unrealized_pnl=_to_float_or_none(p.get("unrealizedPnl")),
                                    leverage=_to_float_or_none(p.get("leverage")),
                                    margin_mode=_to_str_or_none(p.get("marginMode")),
                                )
                            )
                except Exception:
                    # позиционку не считаем критичной: баланс отдали — уже хорошо
                    pass

            return PortfolioState(
                exchange=exchange_id,
                fetched_at=fetched_at,
                balances=balances,
                positions=positions,
                raw={
                    "balance": _safe_trim(bal_raw),
                    # positions_raw лучше не возвращать без нужды
                },
            )

        finally:
            # Важно закрывать соединения ccxt
            try:
                await exchange.close()
            except Exception:
                pass
