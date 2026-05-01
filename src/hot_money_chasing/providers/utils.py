"""Provider helper utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if hasattr(value, "item"):
            value = value.item()
        text = str(value).replace(",", "").replace("%", "").strip()
        if text in ("", "-", "--", "nan", "None"):
            return default
        return float(text)
    except Exception:
        return default


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".")[0]
    return text.zfill(6) if text.isdigit() else text


def first_value(row: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None and str(value) != "nan":
            return value
    return default


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
