from __future__ import annotations

from typing import Any, Optional


def _to_float_or_none(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _to_str_or_none(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _safe_trim(obj: Any, *, max_items: int = 200) -> Any:
    """
    Лёгкая защита от гигантских payload в raw.
    """
    if isinstance(obj, dict):
        out = {}
        for i, (k, v) in enumerate(obj.items()):
            if i >= max_items:
                out["__trimmed__"] = True
                break
            out[str(k)] = v
        return out
    if isinstance(obj, list):
        return obj[:max_items]
    return obj
