"""Composite provider that falls back across multiple data sources."""

from __future__ import annotations

from typing import Callable, List, Sequence, TypeVar

from ..models import MoneyFlow, NewsItem, Quote, SectorFlow, WatchItem
from .base import MarketDataProvider

T = TypeVar("T")


class CompositeProvider(MarketDataProvider):
    name = "composite"

    def __init__(self, providers: Sequence[MarketDataProvider]) -> None:
        self.providers = list(providers)

    def _first_non_empty(self, method: str, *args) -> List[T]:
        last_error = None
        for provider in self.providers:
            try:
                fn: Callable[..., List[T]] = getattr(provider, method)
                values = fn(*args)
            except Exception as exc:
                last_error = exc
                continue
            if values:
                return values
        if last_error:
            raise RuntimeError("all providers failed for %s: %s" % (method, last_error))
        return []

    def fetch_quotes(self, watchlist: Sequence[WatchItem]) -> List[Quote]:
        return self._first_non_empty("fetch_quotes", watchlist)

    def fetch_money_flows(self, watchlist: Sequence[WatchItem]) -> List[MoneyFlow]:
        return self._first_non_empty("fetch_money_flows", watchlist)

    def fetch_sector_flows(self) -> List[SectorFlow]:
        return self._first_non_empty("fetch_sector_flows")

    def fetch_news(self, watchlist: Sequence[WatchItem], limit: int = 30) -> List[NewsItem]:
        return self._first_non_empty("fetch_news", watchlist, limit)
