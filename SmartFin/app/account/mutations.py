import strawberry

from app.account.models import User
from app.account.queries import UserType


@strawberry.type
class UserMutations:
    @strawberry.mutation
    def create_user(self, username: str, email: str, password: str, first_name: str = None, last_name: str = None,
                    is_staff: bool = False, is_active: bool = True, has_subscription: bool = False) -> UserType:
        return User.objects.create_user(username=username, email=email, password=password,
                                        first_name=first_name, last_name=last_name, is_staff=is_staff,
                                        is_active=is_active, has_subscription=has_subscription)
