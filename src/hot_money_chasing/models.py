"""Core domain models used by the stock tracking agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


@dataclass
class WatchItem:
    symbol: str
    name: str = ""
    market: str = ""
    sector: str = ""


@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    pct_change: float
    change: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    turnover_rate: float = 0.0
    volume_ratio: float = 0.0
    sector: str = ""
    timestamp: datetime = field(default_factory=now_local)


@dataclass
class MoneyFlow:
    symbol: str
    name: str = ""
    main_net_inflow: float = 0.0
    main_net_inflow_pct: float = 0.0
    super_net_inflow: float = 0.0
    large_net_inflow: float = 0.0
    retail_net_inflow: float = 0.0
    timestamp: datetime = field(default_factory=now_local)


@dataclass
class SectorFlow:
    sector_name: str
    pct_change: float = 0.0
    turnover: float = 0.0
    main_net_inflow: float = 0.0
    rank: int = 0
    timestamp: datetime = field(default_factory=now_local)


@dataclass
class NewsItem:
    title: str
    url: str = ""
    source: str = ""
    published_at: str = ""
    symbols: List[str] = field(default_factory=list)


@dataclass
class StockSnapshot:
    quote: Quote
    money_flow: Optional[MoneyFlow] = None
    news: List[NewsItem] = field(default_factory=list)


@dataclass
class Signal:
    symbol: str
    name: str
    signal_type: str
    level: str
    title: str
    detail: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=now_local)

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(self)


@dataclass
class AgentReport:
    title: str
    summary: str
    generated_at: datetime
    signals: List[Signal] = field(default_factory=list)
    sections: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(self)


@dataclass
class AgentRunResult:
    generated_at: datetime
    snapshots: List[StockSnapshot]
    sector_flows: List[SectorFlow]
    signals: List[Signal]
    report: AgentReport

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(self)


def signal_count_by_level(signals: Iterable[Signal]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for signal in signals:
        counts[signal.level] = counts.get(signal.level, 0) + 1
    return counts
