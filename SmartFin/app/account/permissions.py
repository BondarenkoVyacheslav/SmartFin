from typing import Any, Union, Awaitable

from strawberry import BasePermission, Info


class HasSubscription(BasePermission):
    message = "Hasn't subscription"

    def has_permission(
            self, source: Any, info: Info, **kwargs: Any
    ) -> Union[bool, Awaitable[bool]]:
        user = info.context.request.user
        return user.is_authenticated and user.has_subscription
