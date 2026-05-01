"""Tushare based provider for optional supplemental market data."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Sequence

from ..models import MoneyFlow, NewsItem, Quote, SectorFlow, WatchItem, now_local
from .base import MarketDataProvider
from .utils import first_value, normalize_symbol, to_float


def _to_ts_code(item: WatchItem) -> str:
    symbol = normalize_symbol(item.symbol)
    market = item.market
    if "." in item.symbol:
        return item.symbol.upper()
    if market in ("sh", "sse", "上交所") or symbol.startswith(("6", "9")):
        return "%s.SH" % symbol
    return "%s.SZ" % symbol


class TushareProvider(MarketDataProvider):
    name = "tushare"

    def __init__(self, token: str = "") -> None:
        self.token = token
        self._ts = None
        self._pro = None

    def _client(self):
        if self._ts is None:
            try:
                import tushare as ts  # type: ignore
            except ImportError as exc:
                raise RuntimeError("Tushare is not installed. Run `pip install tushare`.") from exc
            if self.token:
                ts.set_token(self.token)
            self._ts = ts
        return self._ts

    def _pro_client(self):
        if self._pro is None:
            ts = self._client()
            self._pro = ts.pro_api(self.token) if self.token else ts.pro_api()
        return self._pro

    def fetch_quotes(self, watchlist: Sequence[WatchItem]) -> List[Quote]:
        ts = self._client()
        if not hasattr(ts, "realtime_quote"):
            raise RuntimeError("The installed Tushare package has no realtime_quote API.")
        codes = ",".join(_to_ts_code(item) for item in watchlist)
        frame = ts.realtime_quote(ts_code=codes)
        by_symbol: Dict[str, object] = {}
        for _, row in frame.iterrows():
            symbol = normalize_symbol(first_value(row, ["TS_CODE", "ts_code", "代码", "code"]))
            by_symbol[symbol] = row

        quotes: List[Quote] = []
        for item in watchlist:
            row = by_symbol.get(normalize_symbol(item.symbol))
            if row is None:
                continue
            price = to_float(first_value(row, ["PRICE", "price", "现价"]))
            pre_close = to_float(first_value(row, ["PRE_CLOSE", "pre_close", "昨收"]))
            pct_change = ((price - pre_close) / pre_close * 100.0) if pre_close else 0.0
            quotes.append(
                Quote(
                    symbol=normalize_symbol(item.symbol),
                    name=str(first_value(row, ["NAME", "name", "名称"], item.name or "")),
                    price=price,
                    pct_change=pct_change,
                    change=price - pre_close if pre_close else 0.0,
                    volume=to_float(first_value(row, ["VOLUME", "vol", "volume", "成交量"])),
                    amount=to_float(first_value(row, ["AMOUNT", "amount", "成交额"])),
                    turnover_rate=0.0,
                    volume_ratio=0.0,
                    sector=item.sector,
                    timestamp=now_local(),
                )
            )
        return quotes

    def fetch_money_flows(self, watchlist: Sequence[WatchItem]) -> List[MoneyFlow]:
        pro = self._pro_client()
        today = datetime.now().strftime("%Y%m%d")
        flows: List[MoneyFlow] = []
        for item in watchlist:
            try:
                frame = pro.moneyflow(ts_code=_to_ts_code(item), start_date=today, end_date=today)
            except Exception:
                continue
            if frame.empty:
                continue
            row = frame.iloc[0]
            buy_lg = to_float(first_value(row, ["buy_lg_amount"]))
            sell_lg = to_float(first_value(row, ["sell_lg_amount"]))
            buy_elg = to_float(first_value(row, ["buy_elg_amount"]))
            sell_elg = to_float(first_value(row, ["sell_elg_amount"]))
            main = (buy_lg - sell_lg + buy_elg - sell_elg) * 10000.0
            flows.append(
                MoneyFlow(
                    symbol=normalize_symbol(item.symbol),
                    name=item.name,
                    main_net_inflow=main,
                    main_net_inflow_pct=0.0,
                    super_net_inflow=(buy_elg - sell_elg) * 10000.0,
                    large_net_inflow=(buy_lg - sell_lg) * 10000.0,
                    retail_net_inflow=(
                        to_float(first_value(row, ["buy_sm_amount"]))
                        - to_float(first_value(row, ["sell_sm_amount"]))
                    )
                    * 10000.0,
                    timestamp=now_local(),
                )
            )
        return flows

    def fetch_sector_flows(self) -> List[SectorFlow]:
        return []

    def fetch_news(self, watchlist: Sequence[WatchItem], limit: int = 30) -> List[NewsItem]:
        pro = self._pro_client()
        try:
            frame = pro.news(src="sina", start_date=datetime.now().strftime("%Y-%m-%d"))
        except Exception:
            return []
        symbols = {normalize_symbol(item.symbol): item for item in watchlist}
        news: List[NewsItem] = []
        for _, row in frame.head(limit * 3).iterrows():
            title = str(first_value(row, ["title", "新闻标题"], "")).strip()
            matched = [symbol for symbol, item in symbols.items() if item.name and item.name in title]
            if not title or not matched:
                continue
            news.append(
                NewsItem(
                    title=title,
                    url=str(first_value(row, ["url"], "")),
                    source=str(first_value(row, ["src", "source"], "sina")),
                    published_at=str(first_value(row, ["datetime", "pub_time"], "")),
                    symbols=matched,
                )
            )
            if len(news) >= limit:
                break
        return news
