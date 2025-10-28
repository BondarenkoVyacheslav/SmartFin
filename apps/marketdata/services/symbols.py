from typing import List, Tuple
from django.db.models import Q
from apps.marketdata.models import Provider, SymbolMap  # твои модели

def resolve_external_symbols(provider_code: str, internal_symbols: List[str]) -> List[Tuple[str, str]]:
    try:
        prov = Provider.objects.get(code=provider_code)
    except Provider.DoesNotExist:
        return [(s, s) for s in internal_symbols]

    maps = SymbolMap.objects.filter(
        provider=prov,
        internal_symbol__in=internal_symbols
    ).values_list("internal_symbol", "external_symbol")

    mapping = dict(maps)
    return [(s, mapping.get(s, s)) for s in internal_symbols]
