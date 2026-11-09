# Damai Ticket Assistant — 分阶段开发计划

> 原则：**每个阶段结束后暂停，等待用户下一条指令**，不提前实现后续模块。  
> 产品边界始终：开售监控 / 提醒 / 人工打开官方页；**不做抢票与风控对抗**。

配套：[架构设计](architecture.md) · [数据库设计](database_design.md) · [调研报告](research_report.md)

---

## 0. 已完成阶段

| 阶段 | 状态 | 交付 |
|------|------|------|
| 一 · 脚手架 | ✅ | `/workspace/damai-ticket-assistant`、`.venv`、README、requirements、示例配置、最小 `app.main`、Git 初提交 |
| 二 · 开源调研 | ✅ | `docs/research_report.md` |
| 三 · 架构设计 | ✅ | `architecture.md` / `database_design.md` / `development_plan.md` |
| 四 · 存储与模型 | ✅ | config/logging/sqlite/models/TaskService/pytest；入口 `python -m app` |
| 五 · 任务 CRUD | ✅ | 扩展字段、搜索排序、校验、schema v2、持久化测试 |
| 六 · 倒计时与监控 | ✅ | Countdown/Reminders/Monitor/TaskRuntime、fixture 差分、安全暂停 |
| 七 · 通知模块 | ✅ | 多通道、去重、可配置偏移、声音开关、`--test-notify` |
| 八 · 浏览器辅助 | ✅ | Playwright 打开官方/本地页、人工接管、异常通知 |
| 九 · 中文 GUI | ✅ | PySide6 主窗口、任务 CRUD、监控/浏览器按钮、通知设置 |

技术基线：Python **3.13.5**；PySide6 **6.12.0**；playwright **1.64.1**；APScheduler **3.11.3**；PyYAML **6.0.3**；PyInstaller **6.22.3**；sqlite3 标准库。

---

## 1. 总里程碑（用户门控）

```mermaid
flowchart LR
  P1[一 脚手架 ✅] --> P2[二 调研 ✅]
  P2 --> P3[三 架构 ✅]
  P3 --> P4[四 存储与模型]
  P4 --> P5[五 任务+倒计时+调度]
  P5 --> P6[六 通知]
  P6 --> P7[七 监控差分]
  P7 --> P8[八 浏览器辅助+接管]
  P8 --> P9[九 GUI]
  P9 --> P10[十 集成测试与打包草稿]
```

每一阶段结束条件：**代码可测、文档已更新、Git 已提交、汇报后暂停**。

---

## 2. 阶段四 — 存储与领域模型

**目标**：落地 SQLite schema、迁移、dataclass 模型、基础仓储；仍无 GUI/监控抓取。

**任务**：

1. 添加 `app/models.py`、`app/errors.py`、`app/storage/*`。  
2. 执行 version=1 DDL（见数据库设计）。  
3. `TaskRepository` CRUD + 单测。  
4. 扩展 `settings.example.yaml`：`database.path`、`logging`、`url_allowlist`（仅配置，不抓站）。  

**Pytest**：`tests/test_database.py`（建库、外键级联、CRUD）。  
**暂停点**：仓储测通后停止。

---

## 3. 阶段五 — 任务服务 + 倒计时 + APScheduler

**目标**：内存/DB 任务管理；开售前提醒调度；控制台输出。

**任务**：

1. `TaskService`、`CountdownService`、`SchedulerService`。  
2. date 触发器：开售前 offsets + 到点。  
3. 与 Qt 无关的 CLI 演示：`python -m app.main --demo-reminders`。  
4. 文档注明线程模型（BackgroundScheduler）。  

**Pytest**：倒计时边界（即将开售、已过期）；job 注册/取消。  
**暂停点**：控制台能收到模拟到点提醒后停止。

---

## 4. 阶段六 — 通知通道

**目标**：`Notifier` 协议；console + desktop（或托盘占位）+ 可选 webhook。

**任务**：

1. `app/notify/*`。  
2. 通知写入 `notification_logs`。  
3. 密钥/Webhook 仅本地配置。  

**Pytest**：mock notifier；失败通道不阻断其他通道。  
**暂停点**：桌面或控制台通知稳定后停止。

---

## 5. 阶段七 — 公开状态监控（baseline → diff → notify）

**目标**：礼貌轮询与差分；无合规源时支持「夹具/假数据源」开发模式。

**任务**：

1. `MonitorService` + snapshot/baseline 表。  
2. 最小间隔 + jitter；连续失败熔断。  
3. **开发用 FakePublicSource**（本地 HTML 夹具）保证可测。  
4. 真实站点接入需单独门控评审（ToS）；默认可仅手动状态字段。  

**Pytest**：首轮不通知；哈希不变不通知；状态变化通知一次。  
**禁止**：验证码、stealth、私有签名复刻。  
**暂停点**：夹具差分测通后停止；未获指令不接真站。

---

## 6. 阶段八 — BrowserAssist + HumanTakeover

**目标**：Playwright **仅**打开官方 URL；接管后停止自动操作；失败降级系统浏览器。

**任务**：

1. `app/browser/assist.py`、`takeover_service.py`。  
2. `browser_sessions` 审计行。  
3. 文档/UI 文案强调「随后请自行在官方页面购票」。  

**Pytest**：URL 白名单拒绝；接管状态机转换；可用 mock 替代真实浏览器。  
**暂停点**：人工接管流程演示成功后停止。

---

## 7. 阶段九 — PySide6 GUI

**目标**：MainWindow + TaskPanel + Countdown + Tray；信号桥接后台。

**任务**：

1. `app/gui/*`。  
2. 主线程不跑阻塞 I/O。  
3. 显式按钮：「打开官方页」「我要接管」「启用监控」。  
4. 关于页写明非抢票声明。  

**Pytest**：可测逻辑仍放 services；GUI 用 smoke（可选 `QT_QPA_PLATFORM=offscreen`）。  
**暂停点**：基本 UI 可用后停止。

---

## 8. 阶段十 — 集成、文档收尾、打包草稿

**目标**：端到端「创建任务 → 提醒 →（夹具）状态变化通知 → 打开官方页」；`scripts/build_windows.ps1` 草稿；README 完善。

**任务**：

1. 集成测试路径。  
2. PyInstaller 草稿（可不打包 Playwright 浏览器）。  
3. 许可证与第三方声明。  

**暂停点**：发布候选前必须再等用户指令。

---

## 9. Pytest 策略（全局）

| 层级 | 范围 | 工具 |
|------|------|------|
| 单元 | 模型校验、倒计时、diff、状态机 | pytest |
| 存储 | 临时目录 SQLite | pytest tmp_path |
| 服务 | fake clock、fake source、fake notifier | monkeypatch |
| 可选 GUI | offscreen smoke | pytest + env |
| 禁止 | 对真实大麦生产环境做压力轮询的 CI | — |

建议后续在 `requirements.txt` 或 `requirements-dev.txt` 增加：

```text
pytest>=8
```

（实现阶段再提交，本阶段不改依赖也可。）

目录约定：

```text
tests/
  test_database.py
  test_countdown.py
  test_scheduler.py
  test_monitor_diff.py
  test_takeover.py
  test_notifier.py
  fixtures/
    public_sale_pre.html
    public_sale_on.html
```

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 大麦无稳定合法公开 API | 监控难落地 | 默认手动开售提醒；真站接入单独审批 |
| Qt + APScheduler + Playwright 线程复杂度 | 卡顿/竞态 | 架构规定信号桥；单测假时钟 |
| PyInstaller + Playwright 体积 | 包体过大 | 浏览器不打进包；或仅系统浏览器降级 |
| 依赖许可证（LGPL/GPL） | 分发合规 | README/NOTICE 列出；动态链接 PySide6 |
| 范围滑向抢票 | 违规 | PR/阶段检查清单；禁包名与禁依赖扫描 |
| 礼貌间隔仍触发封禁 | 监控失败 | 熔断、加长间隔、用户可见错误 |

---

## 11. 每阶段检查清单（门控）

- [ ] 未引入抢票/绕过类依赖与代码  
- [ ] 测试通过（该阶段范围内）  
- [ ] 文档与 README 链接仍有效  
- [ ] Git 提交信息清晰  
- [ ] **已暂停并等待用户指令**

---

## 12. 下一可执行阶段（待指令）

用户确认后开始 **阶段四：存储与领域模型**。在此之前不创建业务模块实现文件（本阶段仅文档）。
