# config/graphql/context.py
from dataclasses import dataclass
from typing import Any, Dict
from .dataloaders import build_dataloaders

@dataclass
class RequestContext:
    request: Any
    user: Any
    loaders: Dict[str, Any]

async def get_context(request) -> RequestContext:
    return RequestContext(
        request=request,
        user=getattr(request, "user", None),
        loaders=build_dataloaders(),
    )
