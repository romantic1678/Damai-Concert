# Damai Ticket Assistant / 大麦开票助手

Open-sale **monitor / reminder** assistant for Damai (大麦) concert tickets.

大麦演唱会 **开售监控与提醒** 助手（脚手架 + 调研 + 架构设计已完成；业务模块按阶段实现）。

## Scope / 范围

- **Does:** watch open-sale times, poll public listing info (future modules), send reminders.
- **Does NOT:** auto-purchase tickets, bypass anti-bot, multi-account checkout, or any抢票/下单自动化.

本项目 **不会** 自动购票、绕过风控、多账号下单或任何抢票逻辑。

## Requirements

- Python 3.13+
- Independent virtualenv (`.venv`) — does not modify the system Python

## Setup

```bash
cd /workspace/damai-ticket-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (minimal entrypoint)

```bash
source .venv/bin/activate
python -m app.main
```

Expected: a startup banner (project name, monitor/reminder mode, Python version) and exit code 0.

## Config

Copy `config/settings.example.yaml` to `config/settings.yaml` when you add real settings later.
Do not commit secrets.


## GUI / 桌面界面

```bash
python -m app --gui
```

中文主界面：任务列表、倒计时、开始/停止监控、打开官方页、通知设置、系统日志。浏览器操作在后台线程执行，不阻塞界面。

## Browser assist / 浏览器辅助

Playwright opens **allowlisted official pages** (or local mock pages) for **manual** login and browsing.

**Will not:** solve captchas, jump queues, spoof fingerprints, evade anti-bot, call private APIs, auto-pay, or store credentials.

```bash
python -m app --browser-demo          # local mock HTML via 127.0.0.1
python -m app --open-url https://detail.damai.cn/... --headed
```

## Tests

```bash
source .venv/bin/activate
pytest
```

## Docs / 文档

- [系统架构](docs/architecture.md) — 模块边界、接口、Qt/调度并发、安全与 ToS
- [数据库设计](docs/database_design.md) — SQLite 表结构与数据模型
- [开发计划](docs/development_plan.md) — 分阶段实现与门控暂停
- [开源调研](docs/research_report.md) — 技术选型与不建议使用的抢票类项目

## License / note

For personal reminder use via legitimate public information channels only.
