# HotMoneyChasing

基于 OpenClaw、Python、AkShare/Tushare 与本地策略规则构建的 A 股资金实时动向追踪 Agent。系统面向 200+ 自选股的分钟级刷新场景，自动拉取实时行情、主力资金流向、板块资金轮动和相关新闻，识别放量上涨、资金突增、连续净流入等异常信号，并生成盘中提醒与复盘文本。

> 风险提示：本项目只做行情监控、规则预警和文本辅助分析，不构成投资建议。

## 功能

- 自选股行情拉取：支持 AkShare、Tushare 和本地 mock 数据源。
- 资金异动识别：放量上涨、主力资金突增、连续净流入、板块轮动、题材新闻。
- 状态存储：SQLite 保存分钟级 quotes、money_flows 和 signals，便于后续复盘。
- OpenClaw 接入：优先调用 `openclaw agent --message` 生成自然语言报告；未安装 OpenClaw 时自动使用模板报告。
- CLI 运行：支持单次刷新、循环刷新、JSON 输出和报告落盘。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m hot_money_chasing run --once --provider mock
```

本地依赖检查：

```bash
python -m hot_money_chasing doctor
```

使用 AkShare 实盘接口：

```bash
python -m hot_money_chasing run --once --provider akshare --watchlist data/watchlist.example.csv
```

使用 Tushare：

```bash
export TUSHARE_TOKEN=你的token
python -m hot_money_chasing run --once --provider tushare
```

分钟级循环刷新：

```bash
python -m hot_money_chasing run --provider auto --interval 60
```

输出 JSON 或写入报告：

```bash
python -m hot_money_chasing run --once --json
python -m hot_money_chasing run --once --report-out reports/intraday.txt
```

## OpenClaw

代码默认通过 OpenClaw CLI 接入大模型能力：

```bash
openclaw agent --message "生成一段盘中资金异动分析" --local
```

如果系统中没有 `openclaw` 命令，Agent 会自动降级为确定性模板报告，保证监控任务不中断。可在 `config.example.json` 中调整 `openclaw.command`、`openclaw.timeout_seconds`、`openclaw.local`、`openclaw.agent`、`openclaw.session_id` 和 `openclaw.extra_args`。如果你已经运行 OpenClaw Gateway，可把 `local` 设为 `false`，并配置 `session_id`、`agent` 或 `to`。

## 配置

`config.example.json` 包含数据源、刷新间隔、SQLite 路径和策略阈值。核心阈值：

- `price_breakout_pct`：放量上涨最低涨幅。
- `volume_ratio`：放量最低量比。
- `fund_spike_amount`：主力净流入突增金额阈值。
- `fund_spike_pct`：主力净流入占比阈值。
- `continuous_inflow_window`：连续净流入刷新窗口。
- `hot_sector_min_inflow`：板块热度最低主力净流入。

自选股 CSV 字段：

```csv
symbol,name,market,sector
000001,平安银行,sz,银行
300750,宁德时代,sz,新能源汽车
```

## 项目结构

```text
src/hot_money_chasing/
  cli.py                  # 命令行入口
  engine.py               # Agent 编排
  llm.py                  # OpenClaw 生成适配器
  rules.py                # 本地策略规则
  storage.py              # SQLite 存储
  providers/
    akshare_provider.py   # AkShare 行情/资金/新闻
    tushare_provider.py   # Tushare 行情/资金/新闻
    mock_provider.py      # 本地演示和测试
```

## 测试

```bash
PYTHONPATH=src python3 -m unittest
```

## 生产化建议

- 将 `data.provider` 设置为 `auto`，优先 AkShare，配置 Token 后补充 Tushare。
- 用 cron、systemd 或容器编排执行分钟级任务，并把 SQLite 换成 PostgreSQL/ClickHouse 以承载更高吞吐。
- 将 `signals` 推送到企业微信、飞书、邮件或交易看板。
- 对 200+ 股票建议限制每轮新闻抓取数量，避免新闻接口成为瓶颈。
