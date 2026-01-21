from typing import List

import strawberry
from strawberry import auto

from app.account.models import User


@strawberry.django.type(User)
class UserType:
    id: auto
    username: auto
    email: auto
    first_name: auto
    last_name: auto
    is_staff: auto
    is_active: auto
    has_subscription: auto


@strawberry.type
class UserQueries:
    users: List[UserType] = strawberry.django.field()
