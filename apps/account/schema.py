import strawberry
from strawberry.types import Info
from typing import Optional
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from gql.context import RequestContext
from gql.directives import IsAuthenticated
from .types import UserType, AuthPayload, LoginInput
from .services import authenticate_user, create_session_token_for_user, revoke_token, rotate_token

User = get_user_model()

def _map_user(u: User) -> UserType:
    return UserType(id=str(u.id), username=u.get_username(), email=u.email or "", is_active=u.is_active)

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def me(self, info: Info[RequestContext, None]) -> Optional[UserType]:
        return _map_user(info.context.user)

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, info: Info[RequestContext, None], input: LoginInput) -> Optional[AuthPayload]:
        user = await sync_to_async(authenticate_user)(input.username_or_email, input.password)
        if not user:
            return None
        raw, _ = await sync_to_async(create_session_token_for_user)(user.id)
        # (опц.) установить HttpOnly cookie через расширение/ASGI middleware
        return AuthPayload(user=_map_user(user), token=raw)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def logout(self, info: Info[RequestContext, None], token: str) -> bool:
        deleted = await sync_to_async(revoke_token)(token)
        return deleted > 0

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def refresh_token(self, info: Info[RequestContext, None], old_token: str) -> Optional[str]:
        return await sync_to_async(rotate_token)(old_token)

Subscription = None
