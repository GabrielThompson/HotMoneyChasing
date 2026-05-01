"""AkShare based realtime market data provider."""

from __future__ import annotations

from typing import Dict, List, Sequence

from ..models import MoneyFlow, NewsItem, Quote, SectorFlow, WatchItem, now_local
from .base import MarketDataProvider
from .utils import first_value, normalize_symbol, to_float


class AkShareProvider(MarketDataProvider):
    name = "akshare"

    def __init__(self) -> None:
        self._ak = None

    def _client(self):
        if self._ak is None:
            try:
                import akshare as ak  # type: ignore
            except ImportError as exc:
                raise RuntimeError("AkShare is not installed. Run `pip install akshare`.") from exc
            self._ak = ak
        return self._ak

    def fetch_quotes(self, watchlist: Sequence[WatchItem]) -> List[Quote]:
        ak = self._client()
        frame = ak.stock_zh_a_spot_em()
        by_symbol: Dict[str, object] = {}
        for _, row in frame.iterrows():
            symbol = normalize_symbol(first_value(row, ["代码", "股票代码", "symbol", "code"]))
            by_symbol[symbol] = row

        quotes: List[Quote] = []
        for item in watchlist:
            row = by_symbol.get(normalize_symbol(item.symbol))
            if row is None:
                continue
            quotes.append(
                Quote(
                    symbol=item.symbol,
                    name=str(first_value(row, ["名称", "股票简称", "name"], item.name or "")),
                    price=to_float(first_value(row, ["最新价", "price", "现价"])),
                    pct_change=to_float(first_value(row, ["涨跌幅", "pct_chg", "涨幅"])),
                    change=to_float(first_value(row, ["涨跌额", "change"])),
                    volume=to_float(first_value(row, ["成交量", "volume"])),
                    amount=to_float(first_value(row, ["成交额", "amount"])),
                    turnover_rate=to_float(first_value(row, ["换手率", "turnover_rate"])),
                    volume_ratio=to_float(first_value(row, ["量比", "volume_ratio"])),
                    sector=item.sector,
                    timestamp=now_local(),
                )
            )
        return quotes

    def fetch_money_flows(self, watchlist: Sequence[WatchItem]) -> List[MoneyFlow]:
        ak = self._client()
        frame = None
        last_error = None
        for indicator in ("即时", "今日"):
            try:
                frame = ak.stock_individual_fund_flow_rank(indicator=indicator)
                break
            except Exception as exc:
                last_error = exc
        if frame is None:
            raise RuntimeError("AkShare fund flow API failed: %s" % last_error)

        wanted = {normalize_symbol(item.symbol): item for item in watchlist}
        flows: List[MoneyFlow] = []
        for _, row in frame.iterrows():
            symbol = normalize_symbol(first_value(row, ["代码", "股票代码", "symbol", "code"]))
            if symbol not in wanted:
                continue
            item = wanted[symbol]
            name = str(first_value(row, ["名称", "股票简称", "name"], item.name or ""))
            flows.append(
                MoneyFlow(
                    symbol=symbol,
                    name=name,
                    main_net_inflow=to_float(
                        first_value(row, ["主力净流入-净额", "今日主力净流入-净额", "主力净流入", "main_net_inflow"])
                    ),
                    main_net_inflow_pct=to_float(
                        first_value(row, ["主力净流入-净占比", "今日主力净流入-净占比", "主力净流入占比", "main_net_inflow_pct"])
                    ),
                    super_net_inflow=to_float(first_value(row, ["超大单净流入-净额", "超大单净流入", "super_net_inflow"])),
                    large_net_inflow=to_float(first_value(row, ["大单净流入-净额", "大单净流入", "large_net_inflow"])),
                    retail_net_inflow=to_float(first_value(row, ["小单净流入-净额", "小单净流入", "retail_net_inflow"])),
                    timestamp=now_local(),
                )
            )
        return flows

    def fetch_sector_flows(self) -> List[SectorFlow]:
        ak = self._client()
        flows: List[SectorFlow] = []
        last_error = None
        for sector_type in ("行业资金流", "概念资金流"):
            try:
                frame = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)
            except Exception as exc:
                last_error = exc
                continue
            for rank, (_, row) in enumerate(frame.iterrows(), start=1):
                sector_name = str(first_value(row, ["名称", "板块名称", "sector_name"], "")).strip()
                if not sector_name:
                    continue
                flows.append(
                    SectorFlow(
                        sector_name=sector_name,
                        pct_change=to_float(first_value(row, ["今日涨跌幅", "涨跌幅", "pct_change"])),
                        turnover=to_float(first_value(row, ["今日成交额", "成交额", "turnover"])),
                        main_net_inflow=to_float(first_value(row, ["今日主力净流入-净额", "主力净流入-净额", "main_net_inflow"])),
                        rank=rank,
                        timestamp=now_local(),
                    )
                )
        if not flows and last_error:
            raise RuntimeError("AkShare sector flow API failed: %s" % last_error)
        return flows

    def fetch_news(self, watchlist: Sequence[WatchItem], limit: int = 30) -> List[NewsItem]:
        ak = self._client()
        news: List[NewsItem] = []
        for item in list(watchlist)[:limit]:
            try:
                frame = ak.stock_news_em(symbol=item.symbol)
            except Exception:
                continue
            for _, row in frame.head(3).iterrows():
                title = str(first_value(row, ["新闻标题", "标题", "title"], "")).strip()
                if not title:
                    continue
                news.append(
                    NewsItem(
                        title=title,
                        url=str(first_value(row, ["新闻链接", "链接", "url"], "")),
                        source=str(first_value(row, ["文章来源", "来源", "source"], "东方财富")),
                        published_at=str(first_value(row, ["发布时间", "时间", "published_at"], "")),
                        symbols=[item.symbol],
                    )
                )
        return news
