class AlpacaCacheKeys:
    """Single source of truth for Alpaca Market Data Redis keys."""

    KP = "v1:md:stock:usa:alpaca"

    @classmethod
    def stock_quote(cls, symbol: str, feed: str = "iex", currency: str = "USD") -> str:
        return (
            f"{cls.KP}:quote:{symbol.upper()}:"
            f"{(feed or 'iex').lower()}:{(currency or 'USD').upper()}"
        )

    @classmethod
    def index_quote(cls, symbol: str, feed: str = "iex", currency: str = "USD") -> str:
        return (
            f"{cls.KP}:index:{symbol.upper()}:"
            f"{(feed or 'iex').lower()}:{(currency or 'USD').upper()}"
        )
