"""Agent orchestration for data collection, rule evaluation, and reporting."""

from __future__ import annotations

import time
from typing import Dict, List, Sequence

from .llm import OpenClawClient, ReportGenerator
from .models import AgentRunResult, MoneyFlow, NewsItem, StockSnapshot, WatchItem, now_local
from .providers.akshare_provider import AkShareProvider
from .providers.base import MarketDataProvider
from .providers.composite import CompositeProvider
from .providers.mock_provider import MockProvider
from .providers.tushare_provider import TushareProvider
from .rules import RuleEngine
from .settings import Settings, env_token
from .storage import SQLiteStore


def build_provider(settings: Settings) -> MarketDataProvider:
    provider = settings.data.provider.lower()
    if provider == "mock":
        return MockProvider()
    if provider == "akshare":
        return AkShareProvider()
    if provider == "tushare":
        return TushareProvider(token=env_token(settings))
    if provider == "auto":
        providers: List[MarketDataProvider] = [AkShareProvider()]
        token = env_token(settings)
        if token:
            providers.append(TushareProvider(token=token))
        providers.append(MockProvider())
        return CompositeProvider(providers)
    raise ValueError("unknown provider: %s" % settings.data.provider)


class HotMoneyAgent:
    def __init__(self, settings: Settings, provider: MarketDataProvider, store: SQLiteStore) -> None:
        self.settings = settings
        self.provider = provider
        self.store = store
        self.rules = RuleEngine(settings.rules)
        self.reporter = ReportGenerator(OpenClawClient(settings.openclaw))

    def run_once(self, watchlist: Sequence[WatchItem]) -> AgentRunResult:
        quotes = self.provider.fetch_quotes(watchlist)
        flows = self.provider.fetch_money_flows(watchlist)
        sector_flows = self.provider.fetch_sector_flows()
        news = self.provider.fetch_news(watchlist, limit=self.settings.data.news_symbols_per_run)

        flow_by_symbol: Dict[str, MoneyFlow] = {flow.symbol: flow for flow in flows}
        news_by_symbol: Dict[str, List[NewsItem]] = {}
        for item in news:
            for symbol in item.symbols:
                news_by_symbol.setdefault(symbol, []).append(item)

        snapshots = [
            StockSnapshot(
                quote=quote,
                money_flow=flow_by_symbol.get(quote.symbol),
                news=news_by_symbol.get(quote.symbol, []),
            )
            for quote in quotes
        ]
        signals = self.rules.evaluate(snapshots, sector_flows, store=self.store)
        self.store.save_quotes(quotes)
        self.store.save_money_flows(flows)
        self.store.save_signals(signals)
        report = self.reporter.generate_intraday_report(snapshots, sector_flows, signals)
        return AgentRunResult(
            generated_at=now_local(),
            snapshots=snapshots,
            sector_flows=sector_flows,
            signals=signals,
            report=report,
        )

    def run_forever(self, watchlist: Sequence[WatchItem]) -> None:
        while True:
            result = self.run_once(watchlist)
            print(result.report.raw_text)
            print("")
            time.sleep(max(5, int(self.settings.data.refresh_interval_seconds)))
