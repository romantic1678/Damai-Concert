# Damai Ticket Assistant — 测试报告（第十阶段）

> **生成时间**：2026-11-09 18:03:58 Asia/Shanghai（CST）  
> **版本**：0.10.0  
> **原则**：下列数字均来自本机实际 `pytest` 输出（`/tmp/damai-pytest-full.txt`），非臆造。

---

## 1. 环境

| 项 | 值 |
|----|-----|
| OS | Linux x86_64（项目盒） |
| Python | 3.13.5 |
| Pytest | 9.2.0 |
| 虚拟环境 | `/workspace/damai-ticket-assistant/.venv` |
| 工作目录 | `/workspace/damai-ticket-assistant` |
| 平台行（pytest） | `platform linux -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0` |

---

## 2. 执行命令与原始摘要

```bash
cd /workspace/damai-ticket-assistant && .venv/bin/python -m pytest -v --tb=short 2>&1 | tee /tmp/damai-pytest-full.txt
```

**最终结果（修复 notification_logs FK 并补充缺口测试后重跑）：**

```text
collected 64 items
...
============================== 64 passed in 8.02s ==============================
```

| 指标 | 数值 |
|------|------|
| 收集用例 | 64 |
| 通过 | **64** |
| 失败 | **0** |
| 错误 | **0** |
| 跳过 | **0** |
| 总耗时 | **8.02s** |

失败用例：**无**。

---

## 3. 按文件分布

| 文件 | 用例数 | 结果 |
|------|--------|------|
| `tests/test_browser.py` | 10 | 全部通过 |
| `tests/test_config.py` | 4 | 全部通过 |
| `tests/test_countdown_monitor.py` | 12 | 全部通过 |
| `tests/test_database.py` | 2 | 全部通过 |
| `tests/test_gui_smoke.py` | 2 | 全部通过 |
| `tests/test_models.py` | 7 | 全部通过 |
| `tests/test_notify.py` | 9 | 全部通过 |
| `tests/test_phase10_gaps.py` | 4 | 全部通过（本阶段新增） |
| `tests/test_tasks.py` | 14 | 全部通过 |
| **合计** | **64** | **64 passed** |

进度条原文摘录：

```text
tests/test_browser.py ..........                                         [ 15%]
tests/test_config.py ....                                                [ 21%]
tests/test_countdown_monitor.py ............                             [ 40%]
tests/test_database.py ..                                                [ 43%]
tests/test_gui_smoke.py ..                                               [ 46%]
tests/test_models.py .......                                             [ 57%]
tests/test_notify.py .........                                           [ 71%]
tests/test_phase10_gaps.py ....                                          [ 78%]
tests/test_tasks.py ..............                                       [100%]
```

---

## 4. 重点检查项覆盖

| # | 检查点 | 覆盖方式（代表用例） | 结果 |
|---|--------|----------------------|------|
| 1 | 任务新增/修改/删除 | `test_crud_flow` 等 `test_tasks.py` | 通过 |
| 2 | SQLite 持久化 | `test_persistence_across_reopen`；本阶段 `test_shutdown_restart_persists_tasks` | 通过 |
| 3 | 多任务调度 | `test_multi_task_independent_countdowns`；本阶段 `test_multi_task_reminder_schedule_ids` | 通过 |
| 4 | 倒计时准确性（时区） | `test_countdown_remaining_across_timezones` | 通过 |
| 5 | 通知触发与去重 | `tests/test_notify.py`（8 类事件、dedupe、声音关闭） | 通过 |
| 6 | 浏览器启停（本地 mock） | `tests/test_browser.py` + MockBrowserServer | 通过 |
| 7 | 异常 / 安全停止 | `test_safe_stop_on_fetcher_exception`、`test_notify_failure_isolation` | 通过 |
| 8 | GUI 响应 | `test_main_window_offscreen`（`QT_QPA_PLATFORM=offscreen`） | 通过 |
| 9 | 关闭与重启持久化 | `test_shutdown_restart_persists_tasks` | 通过 |
| 10 | 日志完整性 | `test_logging_writes_file`（强制写日志文件并断言标记字符串） | 通过 |

**网络边界**：浏览器与监控测试仅使用 `127.0.0.1` mock / RejectNetworkFetcher；未对真实大麦发起 HTTP。

---

## 5. 本阶段修复

| 问题 | 严重度 | 处理 |
|------|--------|------|
| `notification_logs.task_id` 外键：对不存在的 `concert_tasks.id`（如 demo `task_id=1`）插入失败并打 ERROR 日志 | 中（不崩进程，但污染日志） | `app/notify/base.py`：写日志前检查任务是否存在，不存在则 `task_id=NULL`；新增 `test_notify_log_without_existing_task_id` |

**修复前**：全量 60 passed（第一轮 `/tmp` 记录亦为全绿）。  
**修复后**：全量 **64 passed / 8.02s**（含 4 个缺口测试）。

---

## 6. 已知限制（非失败）

1. GUI 仅为 offscreen 冒烟，完整视觉回归由人工在真实 `DISPLAY` 上检查。  
2. Playwright 测试依赖本机已执行 `playwright install chromium`。  
3. `pytest.ini` 含 `addopts = -q`，与 `-v` 合用时文件级进度为主；摘要行仍明确 `64 passed`。

---

## 7. 结论

第十阶段自动化回归：**全部通过，无失败用例**。产品边界（仅监控/提醒、无自动购票）在测试夹具中保持不变。
