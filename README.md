# Damai Ticket Assistant / 大麦开票助手

Open-sale **monitor / reminder** assistant for Damai (大麦) concert tickets.

大麦演唱会 **开售监控与提醒** 助手（本阶段为项目脚手架）。

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

## License / note

For personal reminder use via legitimate public information channels only.
