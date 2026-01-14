class USAStockCacheKeys:
    """Single source of truth for US stock Redis keys."""

    KP = "v1:md:stock:usa:yahoo"

    @classmethod
    def quote(cls, symbol: str) -> str:
        return f"{cls.KP}:quote:{symbol.upper()}"

    @classmethod
    def ticker(cls, symbol: str) -> str:
        return f"{cls.KP}:ticker:{symbol.upper()}"

    @classmethod
    def tickers_index(cls) -> str:
        return f"{cls.KP}:tickers:all"
