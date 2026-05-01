"""Local strategy rules for detecting abnormal intraday money movement."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import MoneyFlow, SectorFlow, Signal, StockSnapshot
from .settings import RuleSettings
from .storage import SQLiteStore


class RuleEngine:
    def __init__(self, settings: RuleSettings) -> None:
        self.settings = settings

    def evaluate(
        self,
        snapshots: Iterable[StockSnapshot],
        sector_flows: Iterable[SectorFlow],
        store: Optional[SQLiteStore] = None,
    ) -> List[Signal]:
        hot_sectors = self._hot_sector_map(sector_flows)
        signals: List[Signal] = []
        for snapshot in snapshots:
            signals.extend(self._volume_price_breakout(snapshot))
            signals.extend(self._fund_spike(snapshot))
            signals.extend(self._continuous_inflow(snapshot, store))
            signals.extend(self._sector_rotation(snapshot, hot_sectors))
            signals.extend(self._news_heat(snapshot))

        signals.sort(
            key=lambda item: (
                {"critical": 0, "alert": 1, "watch": 2, "info": 3}.get(item.level, 9),
                -float(item.metrics.get("main_net_inflow", 0.0)),
                -float(item.metrics.get("pct_change", 0.0)),
            )
        )
        return signals[: self.settings.max_signals_per_run]

    def _volume_price_breakout(self, snapshot: StockSnapshot) -> List[Signal]:
        quote = snapshot.quote
        if (
            quote.pct_change >= self.settings.price_breakout_pct
            and quote.volume_ratio >= self.settings.volume_ratio
            and quote.amount >= self.settings.min_turnover_amount
        ):
            return [
                Signal(
                    symbol=quote.symbol,
                    name=quote.name,
                    signal_type="volume_price_breakout",
                    level="alert",
                    title="%s 放量上涨 %.2f%%" % (quote.name, quote.pct_change),
                    detail="涨幅 %.2f%%，量比 %.2f，成交额 %.2f 亿元，价格与成交同步放大。"
                    % (quote.pct_change, quote.volume_ratio, quote.amount / 100000000.0),
                    metrics={
                        "pct_change": quote.pct_change,
                        "volume_ratio": quote.volume_ratio,
                        "amount": quote.amount,
                    },
                )
            ]
        return []

    def _fund_spike(self, snapshot: StockSnapshot) -> List[Signal]:
        quote = snapshot.quote
        flow = snapshot.money_flow
        if flow is None:
            return []
        hit_amount = flow.main_net_inflow >= self.settings.fund_spike_amount
        hit_pct = flow.main_net_inflow_pct >= self.settings.fund_spike_pct
        if hit_amount or hit_pct:
            level = "critical" if hit_amount and quote.pct_change >= self.settings.price_breakout_pct else "watch"
            return [
                Signal(
                    symbol=quote.symbol,
                    name=quote.name,
                    signal_type="fund_spike",
                    level=level,
                    title="%s 主力资金突增" % quote.name,
                    detail="主力净流入 %.2f 亿元，占比 %.2f%%，当前涨幅 %.2f%%。"
                    % (flow.main_net_inflow / 100000000.0, flow.main_net_inflow_pct, quote.pct_change),
                    metrics={
                        "main_net_inflow": flow.main_net_inflow,
                        "main_net_inflow_pct": flow.main_net_inflow_pct,
                        "pct_change": quote.pct_change,
                    },
                )
            ]
        return []

    def _continuous_inflow(self, snapshot: StockSnapshot, store: Optional[SQLiteStore]) -> List[Signal]:
        flow = snapshot.money_flow
        if flow is None or store is None:
            return []
        previous = [value for _, value in store.recent_main_inflows(flow.symbol, self.settings.continuous_inflow_window - 1)]
        series = previous + [flow.main_net_inflow]
        if len(series) < self.settings.continuous_inflow_window:
            return []
        if all(value > 0 for value in series) and sum(series) >= self.settings.continuous_inflow_min_total:
            return [
                Signal(
                    symbol=snapshot.quote.symbol,
                    name=snapshot.quote.name,
                    signal_type="continuous_inflow",
                    level="alert",
                    title="%s 连续主力净流入" % snapshot.quote.name,
                    detail="最近 %d 次刷新主力均为净流入，合计 %.2f 亿元。"
                    % (len(series), sum(series) / 100000000.0),
                    metrics={"main_net_inflow_series": series, "main_net_inflow": flow.main_net_inflow},
                )
            ]
        return []

    def _sector_rotation(self, snapshot: StockSnapshot, hot_sectors: Dict[str, SectorFlow]) -> List[Signal]:
        quote = snapshot.quote
        if not quote.sector or quote.sector not in hot_sectors:
            return []
        sector = hot_sectors[quote.sector]
        if quote.pct_change <= 0:
            return []
        return [
            Signal(
                symbol=quote.symbol,
                name=quote.name,
                signal_type="sector_rotation",
                level="watch",
                title="%s 跟随板块轮动" % quote.name,
                detail="%s 排名第 %d，主力净流入 %.2f 亿元，个股涨幅 %.2f%%。"
                % (sector.sector_name, sector.rank, sector.main_net_inflow / 100000000.0, quote.pct_change),
                metrics={
                    "sector": sector.sector_name,
                    "sector_rank": sector.rank,
                    "sector_inflow": sector.main_net_inflow,
                    "pct_change": quote.pct_change,
                },
            )
        ]

    def _news_heat(self, snapshot: StockSnapshot) -> List[Signal]:
        if not snapshot.news:
            return []
        keywords = ("回购", "增持", "订单", "中标", "业绩", "算力", "人工智能", "芯片", "并购")
        hot_titles = [item.title for item in snapshot.news if any(keyword in item.title for keyword in keywords)]
        if not hot_titles:
            return []
        return [
            Signal(
                symbol=snapshot.quote.symbol,
                name=snapshot.quote.name,
                signal_type="news_heat",
                level="info",
                title="%s 出现题材新闻" % snapshot.quote.name,
                detail="相关新闻：%s" % "；".join(hot_titles[:2]),
                metrics={"news_count": len(hot_titles), "pct_change": snapshot.quote.pct_change},
            )
        ]

    def _hot_sector_map(self, sector_flows: Iterable[SectorFlow]) -> Dict[str, SectorFlow]:
        candidates = [
            sector
            for sector in sector_flows
            if sector.main_net_inflow >= self.settings.hot_sector_min_inflow and sector.rank <= self.settings.hot_sector_top_n
        ]
        return {sector.sector_name: sector for sector in candidates}
