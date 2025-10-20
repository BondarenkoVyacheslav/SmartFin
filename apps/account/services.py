import hashlib, secrets
from datetime import timedelta
from typing import Tuple, Optional
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from .models import SessionToken

TOKEN_TTL_HOURS = 24

def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

@transaction.atomic
def create_session_token_for_user(user_id: int) -> Tuple[str, SessionToken]:
    """Возвращает (raw_token, token_obj). raw_token показываем 1 раз клиенту."""
    raw = secrets.token_urlsafe(32)
    tok = SessionToken.objects.create(
        user_id=user_id,
        digest=_digest(raw),
        expires_at=timezone.now() + timedelta(hours=TOKEN_TTL_HOURS),
    )
    return raw, tok

@transaction.atomic
def revoke_token(raw_or_digest: str) -> int:
    d = raw_or_digest if len(raw_or_digest) == 64 else _digest(raw_or_digest)
    return SessionToken.objects.filter(digest=d).delete()[0]

def authenticate_user(username_or_email: str, password: str):
    """Стандартный путь — через django.contrib.auth.authenticate.
       Если логинимся по email — настрой AUTHENTICATION_BACKENDS под это."""
    user = authenticate(username=username_or_email, password=password)
    if not user or not user.is_active:
        return None
    return user

def rotate_token(old_raw: str) -> Optional[str]:
    """Удобно для 'refresh': удаляем старый токен, выдаём новый."""
    from .selectors import get_token_by_digest
    tok = get_token_by_digest(_digest(old_raw))
    if not tok or tok.is_expired():
        return None
    user_id = tok.user_id
    tok.delete()
    new_raw, _ = create_session_token_for_user(user_id)
    return new_raw
