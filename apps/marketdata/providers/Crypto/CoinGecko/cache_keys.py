from __future__ import annotations

from typing import Optional


class CoinGeckoCacheKeys:
    """
    Единая точка правды для всех ключей Redis, связанных с CoinGecko.
    Никаких строк врозь по коду — только через этот класс.
    """

    # Базовый префикс
    KP = "v1:md:crypto:coingecko"

    # ----- simple / базовые -----

    @classmethod
    def simple_price(cls, ids_sig: str, vs_sig: str, opts_sig: str) -> str:
        return f"{cls.KP}:dto:simple:price:{ids_sig}:{vs_sig}:{opts_sig}"

    @classmethod
    def token_price(
        cls,
        platform: str,
        addrs_sig: str,
        vs_sig: str,
        opts_sig: str,
    ) -> str:
        return f"{cls.KP}:simple:token_price:{platform.lower()}:{addrs_sig}:{vs_sig}:{opts_sig}"

    @classmethod
    def supported_vs_currencies(cls) -> str:
        return f"{cls.KP}:simple:supported_vs_currencies"

    # ----- coins -----

    @classmethod
    def coins_list(cls, include_platform: bool) -> str:
        return f"{cls.KP}:coins:list:{'with_platform' if include_platform else 'plain'}"

    @classmethod
    def coins_markets(
        cls,
        vs: str,
        page: int,
        order: str,
        spark: bool,
        pcp: str,
        ids_sig: Optional[str],
        category: Optional[str],
    ) -> str:
        base = f"{cls.KP}:coins:markets:{vs}:{page}:{order}:{'spark' if spark else 'nospark'}:{pcp}"
        if category:
            base += f":cat:{category.lower()}"
        if ids_sig:
            base += f":ids:{ids_sig}"
        return base

    @classmethod
    def coin_detail(cls, coin_id: str) -> str:
        return f"{cls.KP}:coins:{coin_id.lower()}:detail"

    @classmethod
    def coin_tickers(cls, coin_id: str, page: int) -> str:
        return f"{cls.KP}:coins:{coin_id.lower()}:tickers:{page}"

    @classmethod
    def coin_history(
        cls,
        coin_id: str,
        date_ddmmyyyy: str,
        localization: bool,
    ) -> str:
        return (
            f"{cls.KP}:coins:{coin_id.lower()}:history:"
            f"{date_ddmmyyyy}:{'loc' if localization else 'nloc'}"
        )

    # ----- exchanges -----

    @classmethod
    def exchanges(cls, page: int) -> str:
        return f"{cls.KP}:exchanges:page:{page}"

    @classmethod
    def exchanges_list(cls) -> str:
        return f"{cls.KP}:exchanges:list"

    @classmethod
    def exchange_detail(cls, ex_id: str) -> str:
        return f"{cls.KP}:exchanges:{ex_id.lower()}:detail"

    @classmethod
    def exchange_tickers(cls, ex_id: str, page: int) -> str:
        return f"{cls.KP}:exchanges:{ex_id.lower()}:tickers:{page}"

    @classmethod
    def exchange_volume_chart(cls, ex_id: str, days: int) -> str:
        return f"{cls.KP}:exchanges:{ex_id.lower()}:volume_chart:{days}d"

    # ----- derivatives -----

    @classmethod
    def derivatives(cls) -> str:
        return f"{cls.KP}:derivatives"

    @classmethod
    def derivatives_exchanges(cls, page: int) -> str:
        return f"{cls.KP}:derivatives:exchanges:{page}"

    @classmethod
    def derivatives_exchange_detail(cls, ex_id: str) -> str:
        return f"{cls.KP}:derivatives:exchanges:{ex_id.lower()}:detail"

    @classmethod
    def derivatives_exchanges_list(cls) -> str:
        return f"{cls.KP}:derivatives:exchanges:list"

    # ----- прочее -----

    @classmethod
    def exchange_rates(cls) -> str:
        return f"{cls.KP}:exchange_rates"

    @classmethod
    def search(cls, query_sig: str) -> str:
        return f"{cls.KP}:search:{query_sig}"

    @classmethod
    def trending(cls) -> str:
        return f"{cls.KP}:search:trending"

    @classmethod
    def global_data(cls) -> str:
        return f"{cls.KP}:global"

    @classmethod
    def global_defi(cls) -> str:
        return f"{cls.KP}:global:defi"
