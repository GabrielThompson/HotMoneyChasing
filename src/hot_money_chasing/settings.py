"""Configuration loading for the tracking agent."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import WatchItem


@dataclass
class RuleSettings:
    price_breakout_pct: float = 3.0
    volume_ratio: float = 1.8
    min_turnover_amount: float = 30000000.0
    fund_spike_amount: float = 50000000.0
    fund_spike_pct: float = 8.0
    continuous_inflow_window: int = 3
    continuous_inflow_min_total: float = 80000000.0
    hot_sector_top_n: int = 10
    hot_sector_min_inflow: float = 100000000.0
    max_signals_per_run: int = 80


@dataclass
class DataSettings:
    provider: str = "mock"
    refresh_interval_seconds: int = 60
    news_symbols_per_run: int = 30
    database_path: str = "data/hot_money.db"
    tushare_token_env: str = "TUSHARE_TOKEN"


@dataclass
class OpenClawSettings:
    enabled: bool = True
    command: str = "openclaw"
    timeout_seconds: int = 45
    local: bool = True
    agent: str = ""
    session_id: str = ""
    to: str = ""
    thinking: str = ""
    extra_args: List[str] = field(default_factory=list)


@dataclass
class Settings:
    data: DataSettings = field(default_factory=DataSettings)
    rules: RuleSettings = field(default_factory=RuleSettings)
    openclaw: OpenClawSettings = field(default_factory=OpenClawSettings)


def _update_dataclass(instance: Any, values: Dict[str, Any]) -> None:
    fields = getattr(instance, "__dataclass_fields__", {})
    for key, value in values.items():
        if key in fields:
            setattr(instance, key, value)


def load_settings(path: Optional[str]) -> Settings:
    settings = Settings()
    if not path:
        return settings
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if "data" in raw:
        _update_dataclass(settings.data, raw["data"])
    if "rules" in raw:
        _update_dataclass(settings.rules, raw["rules"])
    if "openclaw" in raw:
        _update_dataclass(settings.openclaw, raw["openclaw"])
    return settings


def load_watchlist(path: str) -> List[WatchItem]:
    if not os.path.exists(path):
        raise FileNotFoundError("watchlist not found: %s" % path)

    items: List[WatchItem] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            symbol = (row.get("symbol") or row.get("code") or row.get("代码") or "").strip()
            if not symbol:
                continue
            items.append(
                WatchItem(
                    symbol=symbol.zfill(6) if symbol.isdigit() else symbol,
                    name=(row.get("name") or row.get("名称") or "").strip(),
                    market=(row.get("market") or row.get("市场") or "").strip().lower(),
                    sector=(row.get("sector") or row.get("行业") or "").strip(),
                )
            )
    return items


def env_token(settings: Settings) -> str:
    return os.environ.get(settings.data.tushare_token_env, "").strip()
