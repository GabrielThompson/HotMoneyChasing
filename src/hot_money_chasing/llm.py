"""Natural language generation backed by OpenClaw with a deterministic fallback."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Iterable, List, Optional

from .models import AgentReport, SectorFlow, Signal, StockSnapshot, now_local, signal_count_by_level
from .settings import OpenClawSettings


class OpenClawClient:
    def __init__(self, settings: OpenClawSettings) -> None:
        self.settings = settings

    def available(self) -> bool:
        return bool(self.settings.enabled and shutil.which(self.settings.command))

    def generate(self, prompt: str) -> Optional[str]:
        if not self.available():
            return None
        command = [self.settings.command, "agent", "--message", prompt]
        if self.settings.local:
            command.append("--local")
        if self.settings.agent:
            command.extend(["--agent", self.settings.agent])
        if self.settings.session_id:
            command.extend(["--session-id", self.settings.session_id])
        if self.settings.to:
            command.extend(["--to", self.settings.to])
        if self.settings.thinking:
            command.extend(["--thinking", self.settings.thinking])
        command.extend(list(self.settings.extra_args))
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=self.settings.timeout_seconds,
                check=False,
            )
        except Exception:
            return None
        text = completed.stdout.strip()
        if completed.returncode != 0 or not text:
            return None
        return text


class ReportGenerator:
    def __init__(self, client: OpenClawClient) -> None:
        self.client = client

    def generate_intraday_report(
        self,
        snapshots: List[StockSnapshot],
        sector_flows: List[SectorFlow],
        signals: List[Signal],
    ) -> AgentReport:
        prompt = self._build_prompt(snapshots, sector_flows, signals)
        llm_text = self.client.generate(prompt)
        if llm_text:
            return AgentReport(
                title="盘中资金动向提醒",
                summary=self._first_line(llm_text),
                generated_at=now_local(),
                signals=signals,
                raw_text=llm_text,
                sections={"openclaw": llm_text},
            )
        return self._fallback_report(snapshots, sector_flows, signals)

    def _build_prompt(
        self,
        snapshots: Iterable[StockSnapshot],
        sector_flows: Iterable[SectorFlow],
        signals: Iterable[Signal],
    ) -> str:
        payload = {
            "signals": [signal.to_dict() for signal in list(signals)[:30]],
            "top_quotes": [
                {
                    "symbol": item.quote.symbol,
                    "name": item.quote.name,
                    "pct_change": item.quote.pct_change,
                    "volume_ratio": item.quote.volume_ratio,
                    "amount": item.quote.amount,
                    "sector": item.quote.sector,
                    "main_net_inflow": item.money_flow.main_net_inflow if item.money_flow else None,
                }
                for item in list(snapshots)[:80]
            ],
            "hot_sectors": [
                {
                    "sector": item.sector_name,
                    "rank": item.rank,
                    "pct_change": item.pct_change,
                    "main_net_inflow": item.main_net_inflow,
                }
                for item in list(sector_flows)[:20]
            ],
        }
        return (
            "你是A股盘中资金动向追踪助手。请基于下面JSON生成中文盘中提醒，"
            "要求：1）先给风险提示；2）列出最重要的异常个股；3）解释资金、量价、板块和新闻的联动；"
            "4）输出不超过700字，语气专业克制，不给确定性买卖建议。\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    def _fallback_report(
        self,
        snapshots: List[StockSnapshot],
        sector_flows: List[SectorFlow],
        signals: List[Signal],
    ) -> AgentReport:
        counts = signal_count_by_level(signals)
        top_signals = signals[:8]
        summary = "本次刷新覆盖 %d 只股票，识别 %d 条异常信号。" % (len(snapshots), len(signals))
        if counts:
            summary += " 级别分布：" + "，".join("%s=%d" % (key, value) for key, value in sorted(counts.items())) + "。"
        lines = [
            "风险提示：以下内容由规则与行情数据自动生成，仅用于盯盘线索梳理，不构成投资建议。",
            "",
            summary,
            "",
            "重点信号：",
        ]
        if top_signals:
            for index, signal in enumerate(top_signals, start=1):
                lines.append("%d. [%s] %s：%s" % (index, signal.level, signal.title, signal.detail))
        else:
            lines.append("暂无达到阈值的异常信号。")
        if sector_flows:
            lines.append("")
            lines.append("板块热度：")
            for sector in sector_flows[:5]:
                lines.append(
                    "- %s：排名 %d，涨幅 %.2f%%，主力净流入 %.2f 亿元"
                    % (sector.sector_name, sector.rank, sector.pct_change, sector.main_net_inflow / 100000000.0)
                )
        text = "\n".join(lines)
        return AgentReport(
            title="盘中资金动向提醒",
            summary=summary,
            generated_at=now_local(),
            signals=signals,
            raw_text=text,
            sections={"fallback": text},
        )

    def _first_line(self, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line[:160]
        return "OpenClaw 已生成盘中资金动向提醒。"
