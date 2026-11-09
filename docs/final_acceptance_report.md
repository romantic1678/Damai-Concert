# 大麦开票助手 — 第十二阶段最终验收报告

> **验收时间**：2026-11-09 18:41–18:45 Asia/Shanghai（CST）  
> **产品版本**：0.11.0  
> **验收基准**：GitHub `main` 最新提交 `24efb9ffb4a0b33eb4d7536b8ad9c330b119d4fc`（含 `docs/windows_build_report.md`）；本地工作树源码与标签 `v0.11.0` 指向的 `cc18a7d8d53dd73634b1fb7ca7ba896376839429` 一致，并在之上追加本报告。  
> **产品边界（强制）**：**仅**开售监控 / 提醒 / 人工打开官方页。**不**自动购票、**不**绕过验证码/人机验证/排队/风控、**不**自动支付、**不**多账号抢票。

---

## 0. 诚实性声明（必读）

| 声明 | 说明 |
|------|------|
| Pytest 通过 ≠ 真实购票成功 | 全部自动化用例使用本地 mock / RejectNetworkFetcher / offscreen GUI；**从未**对真实大麦下单或宣称购票成功。 |
| Actions 构建成功 ≠ Windows 桌面实机运行成功 | 运行 [#42600557265](https://github.com/romantic1678/Damai-Concert/actions/runs/42600557265) 已成功产出 Artifact 与 PE EXE；**本环境无可用 Windows 桌面**，未双击启动 GUI，不得等同于实机验收通过。 |
| 公开状态监控 | 默认 `RejectNetworkFetcher`；启用网络标志时仍拒绝真实抓取并记 WARNING。真实站点轮询属「尚未实现 / 未实机验证」。 |

---

## 1. 验收环境

| 项 | 值 |
|----|-----|
| 执行机 | Linux 项目盒（`Linux x86_64`，非 Windows） |
| 用户已注册机器 | 仅 Android `V2324A`（验收时 `connected: false`），**无 Windows 桌面** |
| 本地路径 | `/workspace/damai-ticket-assistant` |
| Python | 3.13.5（`.venv`） |
| Pytest | 9.2.0 |
| 仓库 | https://github.com/romantic1678/Damai-Concert |
| 远程 `main`（验收开始时） | `24efb9f` |
| 本地源码 tip（报告提交前） | `cc18a7d`（= `v0.11.0` 打包源码） |

---

## 2. Pytest 全量结果（本阶段实测）

命令：

```bash
cd /workspace/damai-ticket-assistant && source .venv/bin/activate && pytest -v --tb=short
```

**原始摘要行：**

```text
collected 69 items
...
============================== 69 passed in 7.33s ==============================
```

| 指标 | 数值 |
|------|------|
| 收集用例 | **69** |
| 通过 | **69** |
| 失败 | **0** |
| 错误 | **0** |
| 跳过 | **0** |
| 耗时 | **7.33s** |

按文件：

| 文件 | 用例数 | 结果 |
|------|--------|------|
| `tests/test_browser.py` | 10 | 全部通过 |
| `tests/test_config.py` | 4 | 全部通过 |
| `tests/test_countdown_monitor.py` | 12 | 全部通过 |
| `tests/test_database.py` | 2 | 全部通过 |
| `tests/test_gui_smoke.py` | 2 | 全部通过（`QT_QPA_PLATFORM=offscreen`） |
| `tests/test_models.py` | 7 | 全部通过 |
| `tests/test_notify.py` | 9 | 全部通过 |
| `tests/test_paths.py` | 5 | 全部通过（第十一阶段新增） |
| `tests/test_phase10_gaps.py` | 4 | 全部通过 |
| `tests/test_tasks.py` | 14 | 全部通过 |
| **合计** | **69** | **69 passed** |

相对第十阶段报告（64 passed）：多出 `test_paths.py` 的 5 项（冻结路径 / Playwright 环境），总数 69，与本轮输出一致。

---

## 3. 功能检查矩阵

### 3.1 已完成且实际验证

（本阶段在 Linux 上通过 **代码审阅 + Pytest + 安全 CLI 冒烟** 确认。）

| 能力 | 证据 |
|------|------|
| 启动入口 | `run_app.py` → `app.main`；`python -m app.main --version` → `0.11.0`；模式横幅含 `NO auto-purchase` |
| 配置与模式门控 | `app.mode` 仅允许 `monitor_reminder`；示例配置禁止 purchase/checkout |
| 任务 CRUD / 搜索排序 | `tests/test_tasks.py`（14）全绿；CLI `--seed-mock` / `--list-tasks` 写出可读任务列表 |
| SQLite 持久化 | `test_persistence_across_reopen`、`test_shutdown_restart_persists_tasks`；schema 无 cookies/password 列 |
| 多任务独立倒计时 / 调度 | `test_multi_task_independent_countdowns`、`test_multi_task_reminder_schedule_ids` |
| 暂停 / 恢复 | `test_pause_and_resume` |
| 异常安全停止 | `test_safe_stop_on_fetcher_exception`、`test_notify_failure_isolation`；`Application.shutdown` 关闭浏览器与调度器 |
| 重启恢复 | `test_shutdown_restart_persists_tasks`：shutdown 后再 open 同一 DB，任务仍在 |
| 日志写入 | `test_logging_writes_file`；本轮 `data/logs/app.log` 扫描无 cookie/password/token 命中 |
| 倒计时与提醒去重 | `tests/test_countdown_monitor.py`、`tests/test_notify.py` |
| 浏览器辅助（本地 mock） | Playwright + `MockBrowserServer`；验证码页触发 `HUMAN_TAKEOVER`；`test_manual_login_page_does_not_scrape_password` |
| 人机/验证码/排队交还用户 | `heuristics.needs_human_verification` 匹配 验证码/滑块/排队/人机验证/安全验证/captcha；仅通知，不求解 |
| 无自动支付 / 无 stealth | `assist.py` 模块声明 + 全库扫描无 `place_order`/`solve_captcha`/`stealth` 实现 |
| 敏感信息不入库不入仓 | `.gitignore` 忽略 `settings.yaml`、`*.db`、`*.log`、`.env`；`git ls-files` 无密钥文件；`browser_sessions` 禁止 cookies 列（设计文档 + schema） |
| GUI offscreen 冒烟 | `test_main_window_offscreen` 等 2 项 |
| Windows 打包配置存在性 | `.github/workflows/windows-build.yml`、`scripts/build_windows.ps1`、`DamaiTicketAssistant.spec`、`app/paths.py` |
| Windows Actions 构建事实 | 以 `docs/windows_build_report.md` 为准（见 §5）；**未**在本阶段重下 625 MiB 包 |

### 3.2 已完成但仅模拟验证

| 能力 | 说明 |
|------|------|
| 公开状态监控归一化 | 本地 HTML/JSON fixture + RejectNetworkFetcher；**未**连真实大麦详情页轮询 |
| 浏览器打开「官方页」路径 | 白名单 URL API 存在；测试仅用 `127.0.0.1` mock |
| 桌面通知（plyer） | 通道代码与测试（含失败隔离）；本盒未必弹出真实系统通知气泡 |
| 中文 GUI 布局/文案 | 源码与 offscreen 构造通过；**无**真实 DISPLAY 下的视觉验收 |
| 人机接管通知 | mock 验证页触发 `HUMAN_TAKEOVER_NEEDED`；非真实大麦验证码页 |
| 冻结路径解析 | `test_paths.py` 用假 `sys.frozen` / `_MEIPASS`，非真实 EXE 进程 |

### 3.3 尚未验证

| 项 | 原因 |
|----|------|
| **Windows 桌面实机启动 EXE** | 本环境为 Linux；用户机器列表无 Windows。未检查：GUI 中文显示、任务增删改、DB 读写、打包内 Playwright 启动 |
| Windows 上首次写入 `%LOCALAPPDATA%\DamaiTicketAssistant\` | 仅有路径设计与单元测试，无实机 |
| 真实大麦站点公开页监控效果 | 无 live fetcher；产品有意未实现自动购票相关抓取 |
| 真实 headed 浏览器 + 用户登录流程 | 需人工在 Windows/本机 headed 窗口操作 |
| Artifact 在本阶段的重新下载校验 | 信赖第十一阶段报告中的 `file`/体积记录，避免重复下载约 625 MiB |

### 3.4 尚未实现

| 项 | 说明 |
|----|------|
| 真实大麦公开页 HTTP 抓取器 | `enable_network_fetch` 仍落到 `RejectNetworkFetcher` |
| 自动购票 / 下单 / 支付 | **按产品边界永久不实现** |
| 验证码求解、排队插队、stealth、指纹伪造、私有 mtop API | **按产品边界永久不实现** |
| Cookie / 账号仓库 | **按设计禁止** |
| one-file 单文件 EXE、自动安装程序（MSI/Inno） | 当前为 onedir Artifact，无安装向导 |
| macOS / Linux 桌面打包 | 未提供对应工作流 |

---

## 4. 安全与合规复核（第十二阶段）

在第十阶段 `docs/security_report.md` 基础上复扫：

| 检查项 | 结论 |
|--------|------|
| 明文密码存储 | 未发现；登录夹具仅有空 password 输入框且测试断言不 scrape |
| Cookie / storage_state 落盘 | 未发现；`user_data_dir=None`；schema 无 cookies 列 |
| API Key / Token 提交 | 仓库无 `.env`/密钥；示例配置无密钥字段 |
| 日志泄露 | `data/logs/app.log`：`rg` 无 cookie/password/token/Bearer |
| 自动支付 / 下单 | 无业务代码路径 |
| 验证码/排队/风控 | 仅启发式 → `pause` / `HUMAN_TAKEOVER` + 通知；无 bypass |
| 模式门控 | 非 `monitor_reminder` 被配置层拒绝 |

**残留风险（可接受）**：用户在 Playwright 窗口自行输入的凭据由用户本机会话管理；若将来启用持久化 `user_data_dir`，需文档强调目录权限。扩大 `url_allowlist` 由用户自负。

---

## 5. Windows 打包与 Artifact（引用第十一阶段实绩）

完整细节见 [`docs/windows_build_report.md`](windows_build_report.md)。摘要：

| 项 | 值 |
|----|----|
| 运行 | https://github.com/romantic1678/Damai-Concert/actions/runs/42600557265 |
| 结论 | `success`（约 7 分） |
| 标签 / 源码 | `v0.11.0` → `cc18a7d` |
| Artifact | `DamaiTicketAssistant-windows`（id `13666465294`） |
| 压缩大小 | 655168185 字节 ≈ **624.6 MiB** |
| 解压体积 | ≈ **1.5 GiB**（`dist_mb=1506.99`） |
| EXE | `DamaiTicketAssistant.exe`，5753873 字节，`PE32+ executable (GUI) x86-64` |
| 依赖目录 | `_internal/`（≈798 M，含 PySide6/Python）、`ms-playwright/`（≈720 M，Chromium 等） |
| 过期 | 约 2026-11-23（retention 14 天） |

**完整性结论（基于报告，非本阶段重下）**：onedir 根目录含引导 EXE + `_internal` + `ms-playwright` + `BUILD_OK.txt`；单独拷贝 EXE 不可运行。

### 5.1 体积分析与可选优化（不破坏运行依赖前提下）

当前体积主因：**PySide6 全量 collect_all** + **Playwright Chromium（含 headless_shell / ffmpeg）**。

| 可选优化 | 预期收益 | 风险 / 前提 |
|----------|----------|-------------|
| spec 中收窄 PySide6（排除不用的 Qt 模块 / 翻译 / 示例） | `_internal` 可降数十到数百 MB | 需回归 GUI；勿误删 Qt 平台插件 |
| 不打包 `chromium_headless_shell` / 多余 browser 变体，仅保留 `chromium` win64 | `ms-playwright` 可明显下降 | 确认应用只用 headed Chromium |
| 首次运行再下载浏览器（不随 Artifact） | Artifact 可降至约一半 | 需联网与安装指引；离线体验变差 |
| 改用系统浏览器 + 官方页深链（弱化 Playwright 打包） | 体积大幅下降 | 产品能力变化，需产品决策 |
| UPX | 不推荐 | spec 已 `upx=False`；易误报杀软 |
| onefile | 启动更慢、解压临时目录；体积未必更小 | 与当前 onedir+浏览器旁路策略不契合 |

**本阶段不改打包脚本**，避免为缩体积破坏已成功的 Actions 产物链。

---

## 6. 最终交付目录结构（源码树）

```text
damai-ticket-assistant/
├── .github/workflows/windows-build.yml
├── .gitignore
├── DamaiTicketAssistant.spec
├── README.md
├── pytest.ini
├── requirements.txt
├── run_app.py                 # PyInstaller / 桌面入口
├── app/
│   ├── __main__.py / main.py  # CLI + --gui
│   ├── lifecycle.py           # 启动/安全关闭
│   ├── config.py / paths.py / logging_config.py / models.py
│   ├── browser/               # Playwright 辅助 + 人机接管启发式
│   ├── gui/                   # 中文 PySide6
│   ├── notify/                # 多通道通知 + 去重
│   ├── scheduler/             # APScheduler
│   ├── services/              # 任务/倒计时/监控/runtime
│   └── storage/               # SQLite schema + 仓库
├── config/settings.example.yaml
├── data/                      # 运行时 DB/日志（gitignore，仅 .gitkeep）
├── docs/                      # 架构/安全/测试/Windows/本验收报告
├── scripts/build_windows.ps1
└── tests/                     # 69 项 Pytest + fixtures
```

运行时（未打包）还会生成（均被忽略）：`config/settings.yaml`、`data/app.db`、`data/logs/app.log`。

Windows Artifact 解压后（引用构建报告）：

```text
DamaiTicketAssistant/
├── DamaiTicketAssistant.exe
├── BUILD_OK.txt
├── _internal/          # Qt / Python 运行时
└── ms-playwright/      # Chromium 等
```

---

## 7. 启动方式

### 7.1 Linux / 源码开发

```bash
cd /workspace/damai-ticket-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # 浏览器辅助需要时
python -m app.main                      # 横幅后退出
python -m app --gui                     # 中文桌面 GUI（需 DISPLAY）
python -m app --list-tasks
python -m app --browser-demo            # 仅本地 mock
pytest                                  # 预期 69 passed
```

亦可：`python run_app.py --gui`。

### 7.2 Windows（打包产物）

1. 从 Actions 运行页下载 Artifact `DamaiTicketAssistant-windows`  
2. 解压**整个**目录  
3. 双击 `DamaiTicketAssistant.exe`（无参数时 `run_app.py` 逻辑默认 `--gui`）  
4. 数据目录：`%LOCALAPPDATA%\DamaiTicketAssistant\`（见 `docs/windows_installation.md`）

**本阶段未执行步骤 3–4 的实机验证。**

---

## 8. 安装方式

| 方式 | 状态 |
|------|------|
| 源码 + venv + pip | 已在本盒验证可运行 CLI / Pytest |
| GitHub Actions Artifact 解压即用（onedir） | 构建成功；**桌面启动尚未验证** |
| MSI / 安装向导 / 应用商店 | 未提供 |
| `pip install` 发布到 PyPI | 未提供 |

---

## 9. 已知问题与限制

1. **无 Windows 实机 GUI 验收**（最高优先级遗留）。  
2. **产物体积大**（≈625 MiB 压缩 / ≈1.5 GiB 解压）；见 §5.1。  
3. **Artifact 14 天过期**（约 2026-11-23）；过期后需重新打 tag / `workflow_dispatch`。  
4. PyInstaller 警告：`PySide6.scripts.deploy_lib` / `project_lib`（构建仍成功）。  
5. Actions Node 20 deprecation 注解（未失败）。  
6. 默认监控 **不访问** 真实大麦网络；「公开状态变化」依赖未来合法 fetcher 或人工打开页面。  
7. GUI 自动化仅为 offscreen；字体/中文渲染/主题需人工看一眼。  
8. 本地分支名历史上为 `master`，远程默认分支为 `main`——推送时应对准 `main`。

---

## 10. 验收分类总表（对应任务要求第 9 点）

### 已完成且实际验证

- 69/69 Pytest；CLI 启动与任务列表；SQLite CRUD/重启恢复；多任务调度与安全停止；通知去重与异常隔离；mock 浏览器人机接管；日志/gitignore/schema 安全面；Windows 工作流与 spec 文件存在；引用的 Actions 成功构建记录。

### 已完成但仅模拟验证

- 状态监控（fixture）；官方页打开路径（白名单+mock）；plyer 桌面通知；中文 GUI（offscreen）；冻结路径单元测试。

### 尚未验证

- Windows 桌面 EXE 实机：GUI、中文显示、任务增删改、数据库读写、打包浏览器启动。  
- 真实大麦公开页监控与 headed 登录体验。

### 尚未实现

- Live 公开页 fetcher；安装向导；非 Windows 打包。  
- （永久不做）自动购票、验证码破解、排队/风控绕过、自动支付、Cookie 仓。

### 已知限制和风险

- 见 §9；产品必须保持监控/提醒边界；用户人工操作官方页时的账号安全自负。

---

## 11. 结论与暂停点

**第十二阶段文档与自动化验收完成。**  
在「监控/提醒/人工打开官方页」边界内，Linux 自动化与安全扫描 **通过**；Windows **构建链已证明可产出 EXE**，但 **桌面实机运行明确标为尚未验证**。  

**请验收人确认后**：可在真实 Windows 上下载 Artifact 做一次人工冒烟，再决定是否发版或触发体积优化专项。

**本报告完成后暂停，等待人工验收。**

---

## 附录 A — 关键链接

- 仓库：https://github.com/romantic1678/Damai-Concert  
- Actions 成功运行：https://github.com/romantic1678/Damai-Concert/actions/runs/42600557265  
- Windows 构建报告：`docs/windows_build_report.md`  
- 安全报告：`docs/security_report.md`  
- 测试报告（第十阶段，64 项）：`docs/test_report.md`（本阶段已升至 69）  
- 安装说明：`docs/windows_installation.md`
