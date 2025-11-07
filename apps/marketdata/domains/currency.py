from apps.marketdata.domains.domain import Domain
from typing import (
    Iterable, Sequence, List, Optional, Dict, Any, Literal
)
from datetime import date

class Currency(Domain):
    """FX + макро-ставки ЦБ."""
    def get_fx_rates(self, pairs: Sequence[str], source: Optional[str] = None) -> Dict[str, float]:
        # TODO: cache + provider.get_fx_rates(pairs, source)
        return {}

    def get_policy_rates(self, countries: Sequence[str],
                         on_date: Optional[date] = None, source: Optional[str] = None) -> Dict[str, float]:
        # TODO: cache + provider.get_policy_rates(countries, on_date, source)
        return {}
