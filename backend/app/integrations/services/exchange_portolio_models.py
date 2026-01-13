from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# -----------------------------
# DTO (унифицированный формат)
# -----------------------------

@dataclass(frozen=True)
class ExchangeCredentials:
    """
    Унифицированные креды. В зависимости от биржи используются разные поля.
    - exchange: "bybit" | "okx" | "binance" | ...
    - api_key / api_secret: почти везде
    - passphrase: OKX и некоторые другие
    - subaccount: если поддерживаешь саб-аккаунты (опционально)
    """
    exchange: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    subaccount: Optional[str] = None

    # Не логируй этот объект целиком.


@dataclass(frozen=True)
class BalanceLine:
    asset: str
    free: Optional[float] = None
    used: Optional[float] = None
    total: Optional[float] = None


@dataclass(frozen=True)
class PositionLine:
    symbol: str
    side: Optional[str] = None  # "long"/"short" (как вернул провайдер)
    contracts: Optional[float] = None
    entry_price: Optional[float] = None
    mark_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    leverage: Optional[float] = None
    margin_mode: Optional[str] = None


@dataclass(frozen=True)
class PortfolioState:
    exchange: str
    fetched_at: datetime
    balances: List[BalanceLine] = field(default_factory=list)
    positions: List[PositionLine] = field(default_factory=list)

    # Сырые данные иногда полезно сохранять для дебага,
    # но лучше хранить их отдельно/под флагом, чтобы не раздувать ответы.
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExchangeFetchError:
    exchange: str
    error_type: str
    message: str


@dataclass(frozen=True)
class PortfolioFetchResult:
    states: List[PortfolioState] = field(default_factory=list)
    errors: List[ExchangeFetchError] = field(default_factory=list)
