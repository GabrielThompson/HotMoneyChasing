"""SQLite storage for minute-level market observations and generated signals."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Iterable, List, Tuple

from .models import MoneyFlow, Quote, Signal


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                price REAL,
                pct_change REAL,
                volume REAL,
                amount REAL,
                turnover_rate REAL,
                volume_ratio REAL,
                sector TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_quotes_symbol_ts ON quotes(symbol, ts);

            CREATE TABLE IF NOT EXISTS money_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                main_net_inflow REAL,
                main_net_inflow_pct REAL,
                super_net_inflow REAL,
                large_net_inflow REAL,
                retail_net_inflow REAL
            );
            CREATE INDEX IF NOT EXISTS idx_money_flows_symbol_ts ON money_flows(symbol, ts);

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                signal_type TEXT,
                level TEXT,
                title TEXT,
                detail TEXT,
                metrics_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
            """
        )
        self.conn.commit()

    def save_quotes(self, quotes: Iterable[Quote]) -> None:
        self.conn.executemany(
            """
            INSERT INTO quotes (
                ts, symbol, name, price, pct_change, volume, amount,
                turnover_rate, volume_ratio, sector
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    quote.timestamp.isoformat(),
                    quote.symbol,
                    quote.name,
                    quote.price,
                    quote.pct_change,
                    quote.volume,
                    quote.amount,
                    quote.turnover_rate,
                    quote.volume_ratio,
                    quote.sector,
                )
                for quote in quotes
            ],
        )
        self.conn.commit()

    def save_money_flows(self, flows: Iterable[MoneyFlow]) -> None:
        self.conn.executemany(
            """
            INSERT INTO money_flows (
                ts, symbol, name, main_net_inflow, main_net_inflow_pct,
                super_net_inflow, large_net_inflow, retail_net_inflow
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    flow.timestamp.isoformat(),
                    flow.symbol,
                    flow.name,
                    flow.main_net_inflow,
                    flow.main_net_inflow_pct,
                    flow.super_net_inflow,
                    flow.large_net_inflow,
                    flow.retail_net_inflow,
                )
                for flow in flows
            ],
        )
        self.conn.commit()

    def save_signals(self, signals: Iterable[Signal]) -> None:
        self.conn.executemany(
            """
            INSERT INTO signals (
                ts, symbol, name, signal_type, level, title, detail, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    signal.created_at.isoformat(),
                    signal.symbol,
                    signal.name,
                    signal.signal_type,
                    signal.level,
                    signal.title,
                    signal.detail,
                    json.dumps(signal.metrics, ensure_ascii=False),
                )
                for signal in signals
            ],
        )
        self.conn.commit()

    def recent_main_inflows(self, symbol: str, limit: int) -> List[Tuple[str, float]]:
        rows = self.conn.execute(
            """
            SELECT ts, main_net_inflow
            FROM money_flows
            WHERE symbol = ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (symbol, limit),
        ).fetchall()
        return [(row["ts"], float(row["main_net_inflow"] or 0.0)) for row in rows][::-1]

    def close(self) -> None:
        self.conn.close()
