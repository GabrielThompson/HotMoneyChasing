"""Deterministic provider for local demos and tests."""

from __future__ import annotations

from typing import List, Sequence

from ..models import MoneyFlow, NewsItem, Quote, SectorFlow, WatchItem, now_local
from .base import MarketDataProvider


class MockProvider(MarketDataProvider):
    name = "mock"

    def fetch_quotes(self, watchlist: Sequence[WatchItem]) -> List[Quote]:
        quotes: List[Quote] = []
        for index, item in enumerate(watchlist):
            momentum = 1 + index % 5
            pct_change = 1.2 * momentum
            quotes.append(
                Quote(
                    symbol=item.symbol,
                    name=item.name or "测试股票%s" % item.symbol[-2:],
                    price=10.0 + index + momentum / 10.0,
                    pct_change=pct_change,
                    change=pct_change / 100.0,
                    volume=150000 + index * 1000,
                    amount=35000000 + index * 4500000 + momentum * 8000000,
                    turnover_rate=2.5 + index / 10.0,
                    volume_ratio=1.3 + momentum / 2.0,
                    sector=item.sector or ("人工智能" if index % 2 == 0 else "新能源汽车"),
                    timestamp=now_local(),
                )
            )
        return quotes

    def fetch_money_flows(self, watchlist: Sequence[WatchItem]) -> List[MoneyFlow]:
        flows: List[MoneyFlow] = []
        for index, item in enumerate(watchlist):
            base = 45000000 + (index % 4) * 26000000
            flows.append(
                MoneyFlow(
                    symbol=item.symbol,
                    name=item.name or "测试股票%s" % item.symbol[-2:],
                    main_net_inflow=base,
                    main_net_inflow_pct=4.0 + index % 6,
                    super_net_inflow=base * 0.42,
                    large_net_inflow=base * 0.35,
                    retail_net_inflow=-base * 0.25,
                    timestamp=now_local(),
                )
            )
        return flows

    def fetch_sector_flows(self) -> List[SectorFlow]:
        now = now_local()
        return [
            SectorFlow("人工智能", pct_change=3.8, turnover=92000000000, main_net_inflow=1850000000, rank=1, timestamp=now),
            SectorFlow("新能源汽车", pct_change=2.5, turnover=68000000000, main_net_inflow=980000000, rank=2, timestamp=now),
            SectorFlow("半导体", pct_change=1.8, turnover=51000000000, main_net_inflow=650000000, rank=3, timestamp=now),
        ]

    def fetch_news(self, watchlist: Sequence[WatchItem], limit: int = 30) -> List[NewsItem]:
        news: List[NewsItem] = []
        for item in list(watchlist)[:limit]:
            news.append(
                NewsItem(
                    title="%s 发布回购与订单进展，机构关注度提升" % (item.name or item.symbol),
                    source="mock",
                    published_at=now_local().isoformat(),
                    symbols=[item.symbol],
                )
            )
        return news
