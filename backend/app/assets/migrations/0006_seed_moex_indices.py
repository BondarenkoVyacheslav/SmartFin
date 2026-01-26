from django.db import migrations


MOEX_INDICES = [
    {
        "secid": "IMOEX",
        "name": "Индекс МосБиржи",
        "shortname": "Индекс МосБиржи",
        "currency": "RUB",
    },
    {
        "secid": "IMOEX2",
        "name": "IMOEX2 – значения индекса МосБиржи за весь торговый день, включая дополнительные сессии",
        "shortname": "Индекс МосБиржи (все сессии)",
        "currency": "RUB",
    },
    {
        "secid": "MECHTR",
        "name": "Индекс МосБиржи химии и нефтехимии полной доходности «брутто»",
        "shortname": "MOEX Chemicals Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MECHTRN",
        "name": "Индекс МосБиржи химии и нефтехимии полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Chemicals Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MECHTRR",
        "name": "Индекс МосБиржи химии и нефтехимии полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Chemicals Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MECNTR",
        "name": "Индекс МосБиржи потребительского сектора полной доходности «брутто»",
        "shortname": "MOEX Consumer Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MECNTRN",
        "name": "Индекс МосБиржи потребит. сектора полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Consumer Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MECNTRR",
        "name": "Индекс МосБиржи потреб. сектора полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Consumer Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MEEUTR",
        "name": "Индекс МосБиржи электроэнергетики полной доходности «брутто»",
        "shortname": "MOEX El.Utilities Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MEEUTRN",
        "name": "Индекс МосБиржи электроэнергетики полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX El. Utilities Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MEEUTRR",
        "name": "Индекс МосБиржи электроэнергетики полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX El. Utilities Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MEFNTR",
        "name": "Индекс МосБиржи финансов полной доходности «брутто»",
        "shortname": "MOEX Financials Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MEFNTRN",
        "name": "Индекс МосБиржи финансов полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Financials Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MEFNTRR",
        "name": "Индекс МосБиржи финансов полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Financials Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MEMMTR",
        "name": "Индекс МосБиржи металлов и добычи полной доходности «брутто»",
        "shortname": "MOEX Metals & Min Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MEMMTRN",
        "name": "Индекс МосБиржи металлов и добычи полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Metals & Mining Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MEMMTRR",
        "name": "Индекс МосБиржи металлов и добычи полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Metals & Min Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MEOGTR",
        "name": "Индекс МосБиржи нефти и газа полной доходности «брутто»",
        "shortname": "MOEX Oil & Gas Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MEOGTRN",
        "name": "Индекс МосБиржи нефти и газа полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Oil & Gas Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MEOGTRR",
        "name": "Индекс МосБиржи нефти и газа полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Oil & Gas Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MESMTR",
        "name": "Индекс МосБиржи средней и малой капитализации полной доходности «брутто»",
        "shortname": "MOEX SMID Total Return",
        "currency": "RUB",
    },
    {
        "secid": "MESMTRN",
        "name": "Индекс МосБиржи средней капитализации полной доходности «нетто» (по нал.ставкам ин.орг-й)",
        "shortname": "MOEX SMID Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "MESMTRR",
        "name": "Индекс МосБиржи средней капитализации полной доходности «нетто» (по нал.ставкам рос.орг-й)",
        "shortname": "MOEX SMID Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "METLTR",
        "name": "Индекс МосБиржи телекоммуникаций полной доходности «брутто»",
        "shortname": "MOEX Telecom Total Return",
        "currency": "RUB",
    },
    {
        "secid": "METLTRN",
        "name": "Индекс МосБиржи телекоммуникаций полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Telecom Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "METLTRR",
        "name": "Индекс МосБиржи телекоммуникаций полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Telecom Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "METNTR",
        "name": "Индекс МосБиржи транспорта полной доходности «брутто»",
        "shortname": "MOEX Transport Total Return",
        "currency": "RUB",
    },
    {
        "secid": "METNTRN",
        "name": "Индекс МосБиржи транспорта полной доходности «нетто» (по налог.ставкам ин.орг-й)",
        "shortname": "MOEX Transport Net TR-NR",
        "currency": "RUB",
    },
    {
        "secid": "METNTRR",
        "name": "Индекс МосБиржи транспорта полной доходности «нетто» (по налог.ставкам рос.орг-й)",
        "shortname": "MOEX Transport Net TR-Res",
        "currency": "RUB",
    },
    {
        "secid": "MICEXBORR1W",
        "name": "ММВБ РЕПО обл 7 дней",
        "shortname": "MCX BO 1W",
        "currency": "RUB",
    },
    {
        "secid": "MICEXBORR2W",
        "name": "ММВБ РЕПО обл 14 дней",
        "shortname": "MCX BO 2W",
        "currency": "RUB",
    },
    {
        "secid": "MICEXBORRON",
        "name": "ММВБ РЕПО обл 1 день",
        "shortname": "MCX BO ON",
        "currency": "RUB",
    },
    {
        "secid": "MICEXEQRR1W",
        "name": "ММВБ РЕПО акц 7 дней",
        "shortname": "MCX EQ 1W",
        "currency": "RUB",
    },
    {
        "secid": "MICEXEQRR2W",
        "name": "ММВБ РЕПО акц 14 дней",
        "shortname": "MCX EQ 2W",
        "currency": "RUB",
    },
    {
        "secid": "MICEXEQRRON",
        "name": "ММВБ РЕПО акц 1 день",
        "shortname": "MCX EQ ON",
        "currency": "RUB",
    },
    {
        "secid": "MOEX10",
        "name": "Индекс МосБиржи 10",
        "shortname": "Индекс МосБиржи 10",
        "currency": "RUB",
    },
    {
        "secid": "MOEXBMI",
        "name": "Индекс МосБиржи широкого рынка",
        "shortname": "Индекс широкого рынка",
        "currency": "RUB",
    },
    {
        "secid": "MOEXCH",
        "name": "Индекс МосБиржи химии и нефтехимии",
        "shortname": "Индекс химии и нефтехимии",
        "currency": "RUB",
    },
    {
        "secid": "MOEXCN",
        "name": "Индекс МосБиржи потребительского сектора",
        "shortname": "Индекс потребительского сектора / Индекс потребит сектора",
        "currency": "RUB",
    },
    {
        "secid": "MOEXEU",
        "name": "Индекс МосБиржи электроэнергетики",
        "shortname": "Индекс электроэнергетики",
        "currency": "RUB",
    },
    {
        "secid": "MOEXFN",
        "name": "Индекс МосБиржи финансов",
        "shortname": "Индекс финансов",
        "currency": "RUB",
    },
    {
        "secid": "MOEXINN",
        "name": "Индекс МосБиржи инноваций",
        "shortname": "Индекс МосБиржи инноваций",
        "currency": "RUB",
    },
    {
        "secid": "MOEXMM",
        "name": "Индекс МосБиржи металлов и добычи",
        "shortname": "Индекс металлов и добычи",
        "currency": "RUB",
    },
    {
        "secid": "MOEXOG",
        "name": "Индекс МосБиржи нефти и газа",
        "shortname": "Индекс нефти и газа",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPO",
        "name": "MOEXREPO обл 12:30",
        "shortname": "MXREPO",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPO1W",
        "name": "MOEXREPO 1 неделя 12:30",
        "shortname": "MOEXREPO1W",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPO1WE",
        "name": "MOEXREPO 1 неделя 19:00",
        "shortname": "MOEXREPO1WE",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPOE",
        "name": "MOEXREPO обл 19:00",
        "shortname": "MXREPOE",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPOEQ",
        "name": "MOEXREPO акц 12:30",
        "shortname": "MXREPOEQ",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPOEQE",
        "name": "MOEXREPO акц 19:00",
        "shortname": "MXREPOEQE",
        "currency": "RUB",
    },
    {
        "secid": "MOEXREPOUSD",
        "name": "MOEXREPO USD 12:30",
        "shortname": "MOEXREPOUSD",
        "currency": "USD",
    },
    {
        "secid": "MOEXREPOUSDE",
        "name": "MOEXREPO USD 19:00",
        "shortname": "MOEXREPOUSDE",
        "currency": "USD",
    },
    {
        "secid": "MOEXTL",
        "name": "Индекс МосБиржи телекоммуникаций",
        "shortname": "Индекс телекоммуникаций",
        "currency": "RUB",
    },
    {
        "secid": "MOEXTN",
        "name": "Индекс МосБиржи транспорта",
        "shortname": "Индекс транспорта",
        "currency": "RUB",
    },
    {
        "secid": "MRBC",
        "name": "Индекс МосБиржи 15",
        "shortname": "Индекс МосБиржи 15",
        "currency": "RUB",
    },
    {
        "secid": "RGBI",
        "name": "Индекс Мосбиржи государственных облигаций ценовой",
        "shortname": "Индекс Мосбиржи гос обл RGBI",
        "currency": "RUB",
    },
    {
        "secid": "RGBITR",
        "name": "Индекс Мосбиржи государственных облигаций",
        "shortname": "Индекс Мосбиржи гос обл RGBITR",
        "currency": "RUB",
    },
    {
        "secid": "RPGCC",
        "name": "MOEXREPO КСУ 12:30",
        "shortname": "MOEXREPOGCC",
        "currency": "RUB",
    },
    {
        "secid": "RPGCC1W",
        "name": "MOEXREPO КСУ 1 неделя 12:30",
        "shortname": "MOEXREPOGCC1W",
        "currency": "RUB",
    },
    {
        "secid": "RPGCC1WE",
        "name": "MOEXREPO КСУ 1 неделя 19:00",
        "shortname": "MOEXREPOGCC1WE",
        "currency": "RUB",
    },
    {
        "secid": "RPGCCE",
        "name": "MOEXREPO КСУ 19:00",
        "shortname": "MOEXREPOGCCE",
        "currency": "RUB",
    },
    {
        "secid": "RUCBCP3Y",
        "name": "Индекс Мосбиржи корпоративных облигаций MOEX 1 - 3 ценовой",
        "shortname": "Индекс Мосбиржи корп обл CBICP 3-5",
        "currency": "RUB",
    },
    {
        "secid": "RUCBCP5Y",
        "name": "Индекс Мосбиржи корпоративных облигаций ценовой 3-5",
        "shortname": "Индекс Мосбиржи корп обл CBICP 1-3",
        "currency": "RUB",
    },
    {
        "secid": "RUCBICP",
        "name": "Индекс Мосбиржи корпоративных облигаций ценовой",
        "shortname": "Индекс Мосбиржи корп обл CBICP",
        "currency": "RUB",
    },
    {
        "secid": "RUCBITR",
        "name": "Индекс Мосбиржи корпоративных облигаций",
        "shortname": "Индекс Мосбиржи корп обл CBITR",
        "currency": "RUB",
    },
    {
        "secid": "RUCBTR3Y",
        "name": "Индекс Мосбиржи корпоративных облигаций MOEX 1-3",
        "shortname": "Индекс Мосбиржи корп обл CBITR 3-5",
        "currency": "RUB",
    },
    {
        "secid": "RUCBTR5Y",
        "name": "Индекс Мосбиржи корпоративных облигаций 3-5",
        "shortname": "Индекс Мосбиржи корп обл CBITR 1-3",
        "currency": "RUB",
    },
    {
        "secid": "RUMBICP",
        "name": "Индекс Мосбиржи муниципальных облигаций ценовой",
        "shortname": "Индекс Мосбиржи мун обл MOEX MBICP",
        "currency": "RUB",
    },
    {
        "secid": "RUMBITR",
        "name": "Индекс Мосбиржи муниципальных облигаций",
        "shortname": "Индекс Мосбиржи мун обл MBITR",
        "currency": "RUB",
    },
]


def _pick_name(name: str, shortname: str) -> str:
    if name and len(name) <= 255:
        return name
    if shortname and len(shortname) <= 255:
        return shortname
    if name:
        return name[:255]
    return (shortname or "MOEX Index")[:255]


def seed_moex_indices(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="index").first()
        or AssetType.objects.filter(name="Индексы").first()
    )
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name="Индексы",
            code="index",
            description="Фондовые и иные индексы",
        )

    for item in MOEX_INDICES:
        symbol = item["secid"]
        market_url = f"moex-index:{symbol}"
        name = _pick_name(item.get("name"), item.get("shortname"))
        currency = item.get("currency") or "RUB"

        Asset.objects.update_or_create(
            symbol=symbol,
            asset_type=asset_type,
            defaults={
                "name": name,
                "market_url": market_url,
                "currency": currency,
            },
        )


def unseed_moex_indices(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="index").first()
        or AssetType.objects.filter(name="Индексы").first()
    )
    if asset_type is None:
        return

    symbols = [item["secid"] for item in MOEX_INDICES]
    Asset.objects.filter(asset_type=asset_type, symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0005_schema_and_table_names"),
    ]

    operations = [
        migrations.RunPython(seed_moex_indices, reverse_code=unseed_moex_indices),
    ]
