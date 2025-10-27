# config/graphql_collector/directives.py
from typing import Any
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info
from config.graphql.context import RequestContext

class IsAuthenticated(BasePermission):
    message = "Authentication required"
    def has_permission(self, source: Any, info: Info[RequestContext, None], **kwargs) -> bool:
        return bool(getattr(info.context, "user", None) and info.context.user.is_authenticated)

class HasRole(BasePermission):
    def __init__(self, role: str) -> None:
        self.role = role
    @property
    def message(self) -> str:
        return f"Required role: {self.role}"
    def has_permission(self, source: Any, info: Info[RequestContext, None], **kwargs) -> bool:
        user = getattr(info.context, "user", None)
        # адаптируй под свою модель ролей
        return bool(user and user.is_authenticated and getattr(user, "role", None) == self.role)

# (опционально) rate-limit как обёртка (упрощённый пример-стаб):
def rate_limited(limit: int):
    def deco(resolver):
        async def wrapped(*args, **kwargs):
            # здесь можно проверить/инкрементнуть счётчик в Redis по (user, field)
            # и бросить исключение при превышении
            return await resolver(*args, **kwargs)
        return wrapped
    return deco
