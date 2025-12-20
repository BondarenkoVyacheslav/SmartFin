from django.db import migrations


def seed_assets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    def _get_asset_type(pk: int, name: str):
        """
        Пытаемся получить по pk (как ты перечислил 1..8).
        Если pk не совпал (например, уже были записи в БД) — берём по name.
        """
        try:
            return AssetType.objects.get(pk=pk)
        except AssetType.DoesNotExist:
            return AssetType.objects.get(name=name)

    # ВАЖНО: pk берём по твоей таблице:
    # 1 Криптовалюты, 2 Акции РФ, 3 Акции США, 4 Фиат, 7 Валюты
    at_crypto = _get_asset_type(1, "Криптовалюты")
    at_ru = _get_asset_type(2, "Акции РФ")
    at_us = _get_asset_type(3, "Акции США")
    at_fiat = _get_asset_type(4, "Фиат")
    at_fx = _get_asset_type(7, "Валюты")

    assets = [
        # -----------------------
        # CRYPTO (CoinGecko pages)
        # currency = валюта котирования/оценки (для MVP удобно USD)
        # -----------------------
        ("Bitcoin", "BTC", at_crypto, "https://www.coingecko.com/en/coins/bitcoin", "USD"),
        ("Ethereum", "ETH", at_crypto, "https://www.coingecko.com/en/coins/ethereum", "USD"),
        ("Tether", "USDT", at_crypto, "https://www.coingecko.com/en/coins/tether", "USD"),
        ("USD Coin", "USDC", at_crypto, "https://www.coingecko.com/en/coins/usd-coin", "USD"),
        ("BNB", "BNB", at_crypto, "https://www.coingecko.com/en/coins/bnb", "USD"),
        ("Solana", "SOL", at_crypto, "https://www.coingecko.com/en/coins/solana", "USD"),
        ("XRP", "XRP", at_crypto, "https://www.coingecko.com/en/coins/xrp", "USD"),
        ("Cardano", "ADA", at_crypto, "https://www.coingecko.com/en/coins/cardano", "USD"),
        ("Dogecoin", "DOGE", at_crypto, "https://www.coingecko.com/en/coins/dogecoin", "USD"),
        ("TRON", "TRX", at_crypto, "https://www.coingecko.com/en/coins/tron", "USD"),
        ("The Open Network", "TON", at_crypto, "https://www.coingecko.com/en/coins/the-open-network", "USD"),
        ("Polkadot", "DOT", at_crypto, "https://www.coingecko.com/en/coins/polkadot", "USD"),
        ("Avalanche", "AVAX", at_crypto, "https://www.coingecko.com/en/coins/avalanche-2", "USD"),
        ("Polygon", "MATIC", at_crypto, "https://www.coingecko.com/en/coins/polygon-ecosystem-token", "USD"),
        ("Litecoin", "LTC", at_crypto, "https://www.coingecko.com/en/coins/litecoin", "USD"),

        # -----------------------
        # RU STOCKS (MOEX issue pages)
        # currency = RUB
        # -----------------------
        ("Sberbank", "SBER", at_ru, "https://www.moex.com/en/issue.aspx?code=SBER", "RUB"),
        ("Gazprom", "GAZP", at_ru, "https://www.moex.com/en/issue.aspx?code=GAZP", "RUB"),
        ("Lukoil", "LKOH", at_ru, "https://www.moex.com/en/issue.aspx?code=LKOH", "RUB"),
        ("Rosneft", "ROSN", at_ru, "https://www.moex.com/en/issue.aspx?code=ROSN", "RUB"),
        ("Norilsk Nickel", "GMKN", at_ru, "https://www.moex.com/en/issue.aspx?code=GMKN", "RUB"),
        ("Novatek", "NVTK", at_ru, "https://www.moex.com/en/issue.aspx?code=NVTK", "RUB"),
        ("VTB", "VTBR", at_ru, "https://www.moex.com/en/issue.aspx?code=VTBR", "RUB"),
        ("MTS", "MTSS", at_ru, "https://www.moex.com/en/issue.aspx?code=MTSS", "RUB"),
        ("Aeroflot", "AFLT", at_ru, "https://www.moex.com/en/issue.aspx?code=AFLT", "RUB"),
        ("Tatneft", "TATN", at_ru, "https://www.moex.com/en/issue.aspx?code=TATN", "RUB"),
        ("Magnit", "MGNT", at_ru, "https://www.moex.com/en/issue.aspx?code=MGNT", "RUB"),

        # -----------------------
        # US STOCKS (Yahoo Finance)
        # currency = USD
        # -----------------------
        ("Apple", "AAPL", at_us, "https://finance.yahoo.com/quote/AAPL", "USD"),
        ("Microsoft", "MSFT", at_us, "https://finance.yahoo.com/quote/MSFT", "USD"),
        ("Amazon", "AMZN", at_us, "https://finance.yahoo.com/quote/AMZN", "USD"),
        ("Alphabet (Google)", "GOOGL", at_us, "https://finance.yahoo.com/quote/GOOGL", "USD"),
        ("NVIDIA", "NVDA", at_us, "https://finance.yahoo.com/quote/NVDA", "USD"),
        ("Tesla", "TSLA", at_us, "https://finance.yahoo.com/quote/TSLA", "USD"),
        ("Meta", "META", at_us, "https://finance.yahoo.com/quote/META", "USD"),
        ("Berkshire Hathaway", "BRK-B", at_us, "https://finance.yahoo.com/quote/BRK-B", "USD"),
        ("JPMorgan Chase", "JPM", at_us, "https://finance.yahoo.com/quote/JPM", "USD"),
        ("Visa", "V", at_us, "https://finance.yahoo.com/quote/V", "USD"),

        # -----------------------
        # FIAT (как кэш-позиции)
        # market_url — справочная страница (уникальная), currency = код валюты
        # -----------------------
        ("Russian Ruble", "RUB", at_fiat, "https://www.xe.com/currency/rub-russian-ruble/", "RUB"),
        ("US Dollar", "USD", at_fiat, "https://www.xe.com/currency/usd-us-dollar/", "USD"),
        ("Euro", "EUR", at_fiat, "https://www.xe.com/currency/eur-euro/", "EUR"),
        ("British Pound", "GBP", at_fiat, "https://www.xe.com/currency/gbp-british-pound/", "GBP"),
        ("Swiss Franc", "CHF", at_fiat, "https://www.xe.com/currency/chf-swiss-franc/", "CHF"),
        ("Chinese Yuan", "CNY", at_fiat, "https://www.xe.com/currency/cny-chinese-yuan/", "CNY"),
        ("Japanese Yen", "JPY", at_fiat, "https://www.xe.com/currency/jpy-japanese-yen/", "JPY"),

        # -----------------------
        # FX (валютные пары как инструменты)
        # currency = котируемая валюта (quote), чтобы было понятно “в чём цена”
        # -----------------------
        ("USD/RUB", "USDRUB", at_fx, "https://www.tradingview.com/symbols/USDRUB/", "RUB"),
        ("EUR/RUB", "EURRUB", at_fx, "https://www.tradingview.com/symbols/EURRUB/", "RUB"),
        ("CNY/RUB", "CNYRUB", at_fx, "https://www.tradingview.com/symbols/CNYRUB/", "RUB"),
        ("EUR/USD", "EURUSD", at_fx, "https://www.tradingview.com/symbols/EURUSD/", "USD"),
        ("GBP/USD", "GBPUSD", at_fx, "https://www.tradingview.com/symbols/GBPUSD/", "USD"),
        ("USD/JPY", "USDJPY", at_fx, "https://www.tradingview.com/symbols/USDJPY/", "JPY"),
    ]

    # Сидим по symbol (он unique). Если актив уже существует — не трогаем.
    for name, symbol, asset_type, market_url, currency in assets:
        Asset.objects.get_or_create(
            symbol=symbol,
            defaults={
                "name": name,
                "asset_type": asset_type,
                "market_url": market_url,
                "currency": currency,
            },
        )


def unseed_assets(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")

    symbols = [
        # crypto
        "BTC", "ETH", "USDT", "USDC", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "TON", "DOT", "AVAX", "MATIC", "LTC",
        # ru
        "SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "VTBR", "MTSS", "AFLT", "TATN", "MGNT",
        # us
        "AAPL", "MSFT", "AMZN", "GOOGL", "NVDA", "TSLA", "META", "BRK-B", "JPM", "V",
        # fiat
        "RUB", "USD", "EUR", "GBP", "CHF", "CNY", "JPY",
        # fx
        "USDRUB", "EURRUB", "CNYRUB", "EURUSD", "GBPUSD", "USDJPY",
    ]

    Asset.objects.filter(symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_seed_asset_types"),
    ]

    operations = [
        migrations.RunPython(seed_assets, reverse_code=unseed_assets),
    ]
