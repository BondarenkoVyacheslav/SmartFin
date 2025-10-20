# config/graphql/schema.py
from importlib import import_module
from typing import List, Optional, Type
import strawberry
from strawberry.tools import merge_types
from django.conf import settings

APP_PREFIX = "apps."

def _iter_app_schema_modules():
    for app in settings.INSTALLED_APPS:
        if app.startswith(APP_PREFIX):
            try:
                yield import_module(f"{app}.schema")
            except ModuleNotFoundError:
                pass

def _collect(name: str) -> List[Type]:
    out = []
    for m in _iter_app_schema_modules():
        obj = getattr(m, name, None)
        if obj:
            out.append(obj)
    return out

def _merge(name: str, parts: List[Type]) -> Optional[Type]:
    return merge_types(name, tuple(parts)) if parts else None

_query = _collect("Query")
_mutation = _collect("Mutation")
_subscription = _collect("Subscription")

Query = _merge("Query", _query) or strawberry.type(type("Query", (), {}))
Mutation = _merge("Mutation", _mutation) if _mutation else None
Subscription = _merge("Subscription", _subscription) if _subscription else None

kwargs = {"query": Query}
if Mutation: kwargs["mutation"] = Mutation
if Subscription: kwargs["subscription"] = Subscription

schema = strawberry.Schema(**kwargs)
