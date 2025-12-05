from typing import Any, Dict, Optional


class CoinGeckoError(Exception):
    """Base exception for CoinGecko provider."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "COINGECKO_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.original = original

    def __repr__(self) -> str:
        return f"<CoinGeckoError code={self.code} message={self.message}>"


# Specific exceptions (fine-grained)
class CoinGeckoNetworkError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Network error contacting CoinGecko", code="NETWORK", details=details, original=original)


class CoinGeckoNotFoundError(CoinGeckoError):
    def __init__(self, resource: str, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        d = {"resource": resource}
        if details:
            d.update(details)
        super().__init__(f"Resource not found on CoinGecko: {resource}", code="NOT_FOUND", details=d, original=original)


class CoinGeckoRateLimitError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Rate limit exceeded on CoinGecko", code="RATE_LIMIT", details=details, original=original)


class CoinGeckoBadRequestError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Bad request to CoinGecko (400)", code="BAD_REQUEST", details=details, original=original)


class CoinGeckoAuthError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Authentication/authorization error with CoinGecko", code="AUTH", details=details, original=original)


class CoinGeckoInvalidResponseError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Invalid/Unexpected response from CoinGecko", code="INVALID_RESPONSE", details=details, original=original)


class CoinGeckoServerError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("CoinGecko server error (5xx)", code="SERVER_ERROR", details=details, original=original)


class CoinGeckoAccessDeniedError(CoinGeckoError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__("Access denied (CDN/firewall) to CoinGecko", code="ACCESS_DENIED", details=details, original=original)


class CoinGeckoMissingApiKeyError(CoinGeckoAuthError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__(details=details, original=original)
        self.code = "MISSING_API_KEY"


class CoinGeckoInvalidApiKeyError(CoinGeckoAuthError):
    def __init__(self, details: Optional[Dict[str, Any]] = None, original: Optional[Exception] = None):
        super().__init__(details=details, original=original)
        self.code = "INVALID_API_KEY"
