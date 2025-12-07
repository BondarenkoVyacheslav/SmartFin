class MOEXCacheKeys:
    """
        Единая точка правды для всех ключей Redis, связанных с MOEX ISS.
        Никаких строк врозь по коду — только через этот класс.
    """

    # Базовый префикс
    KP = "v1:md:stockRussia:moex"

    @classmethod
    def securities(cls, ):
        pass