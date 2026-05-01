"""Provider interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from ..models import MoneyFlow, NewsItem, Quote, SectorFlow, WatchItem


class MarketDataProvider(ABC):
    name = "base"

    @abstractmethod
    def fetch_quotes(self, watchlist: Sequence[WatchItem]) -> List[Quote]:
        raise NotImplementedError

    @abstractmethod
    def fetch_money_flows(self, watchlist: Sequence[WatchItem]) -> List[MoneyFlow]:
        raise NotImplementedError

    @abstractmethod
    def fetch_sector_flows(self) -> List[SectorFlow]:
        raise NotImplementedError

    @abstractmethod
    def fetch_news(self, watchlist: Sequence[WatchItem], limit: int = 30) -> List[NewsItem]:
        raise NotImplementedError
