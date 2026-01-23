try:
    from .alpaca import AlpacaProvider
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    __all__ = []
else:
    __all__ = ["AlpacaProvider"]
