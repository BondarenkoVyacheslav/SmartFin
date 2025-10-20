import strawberry
from typing import Optional

@strawberry.type
class UserType:
    id: strawberry.ID
    username: str
    email: str
    is_active: bool

@strawberry.type
class AuthPayload:
    user: UserType
    token: str  # raw token (отдаём один раз)

@strawberry.input
class LoginInput:
    username_or_email: str
    password: str
