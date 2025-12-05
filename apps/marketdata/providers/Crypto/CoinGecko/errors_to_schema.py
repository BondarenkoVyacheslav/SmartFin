# apps/marketdata/providers/coingecko/graphql.py
from __future__ import annotations
from typing import Any, Callable, Dict, Optional, NoReturn
import functools
import inspect

from strawberry.exceptions import GraphQLError

from .errors import (
    CoinGeckoError,
    CoinGeckoNotFoundError,
    CoinGeckoRateLimitError,
    CoinGeckoAuthError,
    CoinGeckoNetworkError,
    CoinGeckoInvalidResponseError,
    CoinGeckoBadRequestError,
    CoinGeckoServerError,
)


def _format_extensions(err: CoinGeckoError) -> Dict[str, Any]:
    return {
        "provider": "COINGECKO",
        "providerErrorCode": err.code,
        "providerDetails": err.details,
        "isProviderError": True,
    }


def raise_graphql_for_coingecko(err: CoinGeckoError, *, custom_message: Optional[str] = None) -> NoReturn:
    ext = _format_extensions(err)

    if isinstance(err, CoinGeckoNotFoundError):
        message = custom_message or "Ресурс не найден в CoinGecko."
        code = "EXTERNAL_PROVIDER_NOT_FOUND"
    elif isinstance(err, CoinGeckoRateLimitError):
        message = custom_message or "CoinGecko ограничил количество запросов. Попробуйте позже."
        code = "EXTERNAL_PROVIDER_RATE_LIMIT"
    elif isinstance(err, CoinGeckoAuthError):
        message = custom_message or "Проблема с ключом/правами доступа к CoinGecko."
        code = "EXTERNAL_PROVIDER_AUTH"
    elif isinstance(err, CoinGeckoNetworkError):
        message = custom_message or "CoinGecko недоступен (сетевая ошибка)."
        code = "EXTERNAL_PROVIDER_UNAVAILABLE"
    elif isinstance(err, CoinGeckoInvalidResponseError):
        message = custom_message or "Ответ от CoinGecko в неожиданном формате."
        code = "EXTERNAL_PROVIDER_INVALID_RESPONSE"
    elif isinstance(err, CoinGeckoBadRequestError):
        message = custom_message or "Некорректный запрос к CoinGecko (наш баг)."
        code = "EXTERNAL_PROVIDER_BAD_REQUEST"
    elif isinstance(err, CoinGeckoServerError):
        message = custom_message or "CoinGecko испытывает внутренние проблемы."
        code = "EXTERNAL_PROVIDER_SERVER_ERROR"
    else:
        message = custom_message or "Ошибка внешнего провайдера CoinGecko."
        code = "EXTERNAL_PROVIDER_ERROR"

    extensions = {"code": code, **ext}
    raise GraphQLError(message, extensions=extensions)


def coingecko_handle_errors(custom_not_found_message: Optional[str] = None) -> Callable:
    """
    Декоратор для resolvers: перехватывает CoinGecko* исключения и преобразует в GraphQLError.
    Работает с async и sync функциями.
    """

    def decorator(fn: Callable):
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def _wrapped(*args, **kwargs):
                try:
                    return await fn(*args, **kwargs)
                except CoinGeckoError as e:
                    # если NotFound — передаём кастомный текст
                    if isinstance(e, CoinGeckoNotFoundError):
                        raise_graphql_for_coingecko(e, custom_message=custom_not_found_message)
                    raise_graphql_for_coingecko(e)

            return _wrapped

        else:

            @functools.wraps(fn)
            def _wrapped_sync(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except CoinGeckoError as e:
                    if isinstance(e, CoinGeckoNotFoundError):
                        raise_graphql_for_coingecko(e, custom_message=custom_not_found_message)
                    raise_graphql_for_coingecko(e)

            return _wrapped_sync

    return decorator
