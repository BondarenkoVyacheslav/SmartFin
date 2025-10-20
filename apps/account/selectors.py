from typing import Optional
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from .models import SessionToken

User = get_user_model()

def get_user_by_id(user_id: int) -> Optional[User]:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

def get_token_by_digest(digest: str) -> Optional[SessionToken]:
    try:
        return SessionToken.objects.select_related("user").get(digest=digest)
    except SessionToken.DoesNotExist:
        return None

def active_tokens_for_user_qs(user_id: int) -> QuerySet[SessionToken]:
    return SessionToken.objects.filter(user_id=user_id)
