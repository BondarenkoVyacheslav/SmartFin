class MOEXCacheKeys:
    """
        Единая точка правды для всех ключей Redis, связанных с MOEX ISS.
        Никаких строк врозь по коду — только через этот класс.
    """

    # Базовый префикс
    KP = "v1:md:stock:market:russia:moex"

    @classmethod
    def securities(
            cls,
            *,
            q: str | None = None,
            lang: str | None = None,
            engine: str | None = None,
            is_trading: int | None = None,
            market: str | None = None,
            group_by: str | None = None,
            limit: int | None = None,
            group_by_filter: str | None = None,
            start: int | None = None,
    ) -> str:
        """
        Ключ для кэша /iss/securities.json

        Предполагаем, что все значения уже приведены в порядок в MOEXProvider.
        Здесь только:
        - учитываем хардкап ISS на 100 строк,
        - подставляем дефолты для None.
        """

        # MOEX ISS фактически отдаёт максимум 100 строк
        if limit is None or limit > 100:
            eff_limit = 100
        else:
            eff_limit = limit

        # Старт не может быть отрицательным
        if start is None or start < 0:
            eff_start = 0
        else:
            eff_start = start

        # is_trading: 1 / 0 / any
        if is_trading is None:
            trd = "any"
        else:
            trd = str(int(is_trading))  # 0 или 1

        return (
            f"{cls.KP}:securities:"
            f"q={q or '-'}:"  # поиск/фильтр по строке
            f"lang={lang or 'ru'}:"  # ru / en / и т.д.
            f"engine={engine or '-'}:"  # stock / currency / ...
            f"trd={trd}:"  # 1 / 0 / any
            f"market={market or '-'}:"  # shares / bonds / ...
            f"group_by={group_by or '-'}:"  # type / group / none
            f"group_by_filter={group_by_filter or '-'}:"  # фильтр по group_by
            f"limit={eff_limit}:"
            f"start={eff_start}"
        )

    @classmethod
    def security_detail(cls, security: str) -> str:
        """
            Ключ для деталки по инструменту /iss/securities/{security}.json.

            Параметры:
            - security       — код инструмента (SECID/ISIN/etc.)
        """

        return (
            f"{cls.KP}:securities:"
            f"security={security}"
        )

    @classmethod
    def engines(cls) -> str:
        """
            Ключ для /iss/engines.json
        """

        return (
            f"{cls.KP}:engines"
        )

    @classmethod
    def engine_markets(cls, engine: str) -> str:
        """
            Ключ для /iss/engines/[engine]/markets
        """

        return (
            f"{cls.KP}:engine:"
            f"{engine}:markets"
        )

    @classmethod
    def engine_market_boards(cls, engine: str, market: str) -> str:
        """
            Ключ для /iss/engines/[engine]/markets/[market]/boards
        """

        return (
            f"{cls.KP}:engine:"
            f"{engine}:market:"
            f"{market}:boards"
        )

    @classmethod
    def stock_index_SNDX_securities(cls) -> str:
        """
            Ключ для /iss/engines/[engine]/markets/[market]/boards/[board]/securities
        """

        return (
            f"{cls.KP}:engine:stock:"
            "market:index:"
            "board:SNDX:"
            "securities"
        )