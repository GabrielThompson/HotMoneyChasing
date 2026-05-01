"""Command line interface for HotMoneyChasing."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .engine import HotMoneyAgent, build_provider
from .settings import load_settings, load_watchlist
from .storage import SQLiteStore


def _add_common_args(parser: argparse.ArgumentParser, with_defaults: bool) -> None:
    default = None if with_defaults else argparse.SUPPRESS
    parser.add_argument("--config", default="config.example.json" if with_defaults else default, help="Path to JSON config")
    parser.add_argument(
        "--watchlist",
        default="data/watchlist.example.csv" if with_defaults else default,
        help="Path to watchlist CSV",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "akshare", "tushare", "auto"],
        default=default,
        help="Override data provider",
    )
    parser.add_argument("--db", default=default, help="Override SQLite database path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A-share hot money tracking agent")
    _add_common_args(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run realtime tracking")
    _add_common_args(run, with_defaults=False)
    run.add_argument("--once", action="store_true", help="Run a single refresh and exit")
    run.add_argument("--interval", type=int, help="Refresh interval in seconds")
    run.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    run.add_argument("--report-out", help="Write generated report text to a file")

    doctor = subparsers.add_parser("doctor", help="Check optional runtime dependencies")
    _add_common_args(doctor, with_defaults=False)
    return parser


def _apply_overrides(args: argparse.Namespace, settings) -> None:
    if args.provider:
        settings.data.provider = args.provider
    if args.db:
        settings.data.database_path = args.db
    if getattr(args, "interval", None):
        settings.data.refresh_interval_seconds = args.interval


def run_command(args: argparse.Namespace) -> int:
    settings = load_settings(args.config if os.path.exists(args.config) else None)
    _apply_overrides(args, settings)
    watchlist = load_watchlist(args.watchlist)
    provider = build_provider(settings)
    store = SQLiteStore(settings.data.database_path)
    agent = HotMoneyAgent(settings, provider, store)
    try:
        if args.once:
            result = agent.run_once(watchlist)
            if args.json:
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(result.report.raw_text)
            if args.report_out:
                parent = os.path.dirname(args.report_out)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(args.report_out, "w", encoding="utf-8") as fh:
                    fh.write(result.report.raw_text)
                    fh.write("\n")
            return 0
        agent.run_forever(watchlist)
        return 0
    finally:
        store.close()


def doctor_command(args: argparse.Namespace) -> int:
    settings = load_settings(args.config if os.path.exists(args.config) else None)
    _apply_overrides(args, settings)
    checks = []
    for module_name in ("akshare", "tushare"):
        try:
            __import__(module_name)
            checks.append((module_name, "ok"))
        except ImportError:
            checks.append((module_name, "missing"))
    from .llm import OpenClawClient

    client = OpenClawClient(settings.openclaw)
    checks.append(("openclaw", "ok" if client.available() else "missing"))
    for name, status in checks:
        print("%-10s %s" % (name, status))
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args.command = "run"
        args.once = True
        args.json = False
        args.report_out = None
        args.interval = None
    if args.command == "run":
        return run_command(args)
    if args.command == "doctor":
        return doctor_command(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
