# Damai Ticket Assistant — 开源项目调研报告（第二阶段）

> **项目定位**：合法的大麦 **开售监控 / 提醒** 助手（monitor / reminder only）。  
> **明确不做**：自动下单、验证码绕过、插队、反风控对抗、多账号刷单、任何「抢票」自动化。  
> **数据抓取时间**：2026-11-09 17:18 Asia/Shanghai（GitHub REST API `stargazers_count` / `pushed_at` / `license.spdx_id`）。  
> **时间换算**：文中「最近更新」均为 `pushed_at` 转换为 Asia/Shanghai。

---

## 1. 调研结论（摘要）

1. **桌面壳 + 定时 + 持久化 + 打包** 的技术底座成熟，官方/主流库许可证清晰，可直接采用。
2. **合法「演出信息监控」** 在海外侧多依赖官方 Discovery API（如 Ticketmaster）或公开列表页差分；Star 普遍不高，但架构可借鉴（状态基线 → 差分 → 通知）。
3. **合法「库存/变更监控」** 以 `changedetection.io` 为代表最成熟；Shopify 公开 `.json` 端点类项目可参考「礼貌轮询 + 状态机」，但需遵守站点条款与限速。
4. **大麦（Damai）专项**：GitHub 上绝大多数相关仓库是 **抢票/自动化下单/逆向对抗**；几乎找不到「仅读公开开售信息、许可证清晰、维护活跃」的官方或准官方监控项目。`jianrongfeng/damai-notify` 方向接近开票提醒，但许可证不明、体量极小。`zemojix-0305/ticket-radar` 自称不做下单且拒绝破解验证码，但含 Cookie/非公开接口库存层，**不得整仓引入或复制其请求链**。
5. **推荐技术栈**（见文末）足以支撑本阶段「开售时间提醒 + 公开信息变更通知 + 桌面 GUI」；Playwright 仅用于可选的「打开官方购票页 / 人工确认」，禁止用于绕过风控或自动结账。

---

## 2. 分主题调研

### 2.1 Playwright Python

#### 项目：Playwright for Python（官方）

| 字段 | 内容 |
|------|------|
| 项目名称 | playwright-python |
| GitHub 地址 | https://github.com/microsoft/playwright-python |
| Star 数量 | 15092（抓取于 2026-11-09 17:18 Asia/Shanghai） |
| 最近更新时间 | 2026-11-06 17:44:08 Asia/Shanghai |
| License | Apache-2.0 |
| 技术架构 | Python 绑定 + 独立浏览器驱动（Chromium/Firefox/WebKit）；同步/异步 API |
| 主要功能 | 可靠的浏览器自动化与端到端测试；网络拦截、截图、多浏览器 |
| 可借鉴模块 | **仅**：可选「一键打开官方活动页」、页面快照辅助人工核对开售文案；配置持久化浏览器配置文件的 **用户主动登录** 场景（若未来需要）。测试脚手架也可参考。 |
| 潜在安全问题 | 被滥用于绕过风控/自动下单；保存的 storage state / Cookie 属敏感凭证，需加密与本地权限控制；勿在文档或代码中示范 stealth / 指纹伪装。 |

**结论**：作为官方库强烈推荐纳入依赖；使用边界必须写进 README/架构文档。

---

### 2.2 PySide6（Qt for Python）

#### 项目：Qt for Python / PySide6 源码仓

| 字段 | 内容 |
|------|------|
| 项目名称 | pyside-setup（PySide6 + Shiboken6） |
| GitHub 地址 | https://github.com/pyside/pyside-setup |
| Star 数量 | 137（镜像/超项目；实际使用量远高于此，以 PyPI 与 Qt 官方文档为准） |
| 最近更新时间 | 2026-11-09 05:43:05 Asia/Shanghai |
| License | GitHub API 未返回单一 `spdx_id`；PyPI `PySide6` 标注为 **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**（商业发行需核对 Qt 许可） |
| 技术架构 | Qt6 C++ 框架的官方 Python 绑定；Widgets / QML；信号槽 UI 模型 |
| 主要功能 | 跨平台桌面 GUI、系统托盘、定时器与线程安全信号 |
| 可借鉴模块 | 主窗口、任务列表面板、系统托盘、设置页、QThread/QObject 与监控调度解耦 |
| 潜在安全问题 | LGPL 动态链接义务；打包时需附带许可证文本；勿把密钥硬编码进 UI 资源 |

**官方文档**：https://doc.qt.io/qtforpython-6/  
**结论**：桌面 GUI 首选；与项目已锁定的 `PySide6==6.12.0` 一致。

---

### 2.3 APScheduler

#### 项目：APScheduler

| 字段 | 内容 |
|------|------|
| 项目名称 | APScheduler |
| GitHub 地址 | https://github.com/agronholm/apscheduler |
| Star 数量 | 7697 |
| 最近更新时间 | 2026-10-27 03:55:38 Asia/Shanghai |
| License | MIT |
| 技术架构 | 进程内调度器；触发器（cron / interval / date）；可选 job store（含 SQLAlchemy） |
| 主要功能 | 开售前提醒、周期性轻量轮询、一次性「到点提醒」任务 |
| 可借鉴模块 | `BackgroundScheduler` + date/interval 触发；任务持久化到 SQLite job store；与 GUI 的启停生命周期绑定 |
| 潜在安全问题 | 进程崩溃丢任务（需持久化）；过密 interval 会对目标站点造成压力 → 必须设最小间隔与 jitter；勿把调度用于高频撞库式抢购 |

**结论**：开售提醒与低频监控调度的首选库。

---

### 2.4 SQLite 相关 Python 项目

#### 项目 A：sqlite-utils

| 字段 | 内容 |
|------|------|
| 项目名称 | sqlite-utils |
| GitHub 地址 | https://github.com/simonw/sqlite-utils |
| Star 数量 | 2188 |
| 最近更新时间 | 2026-10-11 08:15:55 Asia/Shanghai |
| License | Apache-2.0 |
| 技术架构 | 标准库 sqlite3 之上的高层库 + CLI |
| 主要功能 | 表/行 CRUD、导入导出、便于运维调试 |
| 可借鉴模块 | 本地事件快照表、已见状态（seen）表的快速搭建与 CLI 排障 |
| 潜在安全问题 | SQL 注入若拼接用户输入；DB 文件权限；勿把 Cookie 明文长期落盘 |

#### 项目 B：SQLAlchemy

| 字段 | 内容 |
|------|------|
| 项目名称 | SQLAlchemy |
| GitHub 地址 | https://github.com/sqlalchemy/sqlalchemy |
| Star 数量 | 12271 |
| 最近更新时间 | 2026-11-08 23:34:18 Asia/Shanghai |
| License | MIT |
| 技术架构 | ORM + Core；方言含 SQLite |
| 主要功能 | 结构化模型、迁移友好、与 APScheduler job store 集成 |
| 可借鉴模块 | `Event` / `WatchTask` / `NotificationLog` 模型；连接池与会话管理 |
| 潜在安全问题 | 过度 ORM 复杂度；迁移不当丢数据；连接串勿含密钥 |

#### 项目 C：aiosqlite

| 字段 | 内容 |
|------|------|
| 项目名称 | aiosqlite |
| GitHub 地址 | https://github.com/omnilib/aiosqlite |
| Star 数量 | 1586 |
| 最近更新时间 | 2026-03-01 23:02:39 Asia/Shanghai |
| License | MIT |
| 技术架构 | asyncio 桥接到标准 sqlite3 |
| 主要功能 | 异步协程中安全访问 SQLite |
| 可借鉴模块 | 若未来监控循环改为 asyncio，可用其避免阻塞事件循环 |
| 潜在安全问题 | 与同步 GUI 混用时注意线程边界；写入并发需 WAL/`timeout` |

**结论**：本阶段优先 **标准库 sqlite3 + 简单 schema**；若模型变复杂再引入 SQLAlchemy。sqlite-utils 适合调试，非运行时硬依赖。

---

### 2.5 PyInstaller

#### 项目：PyInstaller

| 字段 | 内容 |
|------|------|
| 项目名称 | PyInstaller |
| GitHub 地址 | https://github.com/pyinstaller/pyinstaller |
| Star 数量 | 13143 |
| 最近更新时间 | 2026-11-09 04:56:19 Asia/Shanghai |
| License | API 返回 `NOASSERTION`；`COPYING.txt` 实为 **GPL-2.0-or-later + Bootloader Exception**（可将引导加载器与专有代码组合，但需阅读全文） |
| 技术架构 | 分析导入图 → 打包解释器与依赖 → 单文件/单目录可执行文件 |
| 主要功能 | Windows/macOS/Linux 桌面分发 |
| 可借鉴模块 | `scripts/build_windows.ps1` 一类打包脚本；hiddenimports（PySide6、Playwright 驱动需单独策略） |
| 潜在安全问题 | 单文件解压目录可被篡改；勿把密钥打进二进制；Playwright 浏览器体积巨大，通常 **不** 把浏览器打进包，改为文档说明用户安装或「仅打开系统默认浏览器」；GPL 义务需合规披露 |

**结论**：适合 GUI 分发；Playwright 浏览器不建议一并打包。

---

### 2.6 Python 桌面通知项目

#### 项目 A：plyer

| 字段 | 内容 |
|------|------|
| 项目名称 | plyer |
| GitHub 地址 | https://github.com/kivy/plyer |
| Star 数量 | 1805 |
| 最近更新时间 | 2026-10-04 14:45:14 Asia/Shanghai |
| License | MIT |
| 技术架构 | 平台 API 门面（通知、电池、定位等） |
| 主要功能 | 跨平台桌面/移动通知封装 |
| 可借鉴模块 | `plyer.notification.notify` 作为 notifier 后端之一 |
| 潜在安全问题 | 部分桌面环境需额外守护进程；通知内容勿泄露账号 Cookie |

#### 项目 B：notify-py

| 字段 | 内容 |
|------|------|
| 项目名称 | notify-py |
| GitHub 地址 | https://github.com/ms7m/notify-py |
| Star 数量 | 292 |
| 最近更新时间 | 2024-07-10 03:31:17 Asia/Shanghai（维护偏慢） |
| License | MIT |
| 技术架构 | Win10/11 / macOS / Linux(libnotify) 原生通知 |
| 主要功能 | 极简跨平台桌面通知 |
| 可借鉴模块 | 轻量 `Notify().send()` API 设计 |
| 潜在安全问题 | 更新不活跃可能导致新系统兼容问题；无动作按钮 |

#### 项目 C：desktop-notifier

| 字段 | 内容 |
|------|------|
| 项目名称 | desktop-notifier |
| GitHub 地址 | https://github.com/samschott/desktop-notifier |
| Star 数量 | 158 |
| 最近更新时间 | 2026-09-16 23:54:59 Asia/Shanghai |
| License | MIT |
| 技术架构 | 现代跨平台桌面通知库（含异步友好设计） |
| 主要功能 | 标题/正文/图标；部分平台支持交互 |
| 可借鉴模块 | 作为 plyer 的替代后端；与 asyncio 调度配合 |
| 潜在安全问题 | 平台差异仍需实测；权限被系统关闭时需降级到托盘/声音 |

#### 补充：ntfy（推送通道，非纯桌面库）

| 字段 | 内容 |
|------|------|
| 项目名称 | ntfy |
| GitHub 地址 | https://github.com/binwiederhier/ntfy |
| Star 数量 | 35403 |
| 最近更新时间 | 2026-11-09 09:50:46 Asia/Shanghai |
| License | Apache-2.0 |
| 技术架构 | HTTP PUT/POST → 手机/桌面客户端 |
| 主要功能 | 自托管或公共服务推送 |
| 可借鉴模块 | 开售提醒的「第二通道」（离开电脑时） |
| 潜在安全问题 | 公开 topic 可被他人订阅 → 必须用随机私密 topic；自托管鉴权 |

**结论**：桌面侧优先 **PySide6 托盘 + desktop-notifier/plyer**；外出提醒可选用 ntfy/邮件/Webhook，均需用户显式配置。

---

### 2.7 演唱会 / 演出信息监控项目（非抢票）

#### 项目 A：artist-radar

| 字段 | 内容 |
|------|------|
| 项目名称 | artist-radar |
| GitHub 地址 | https://github.com/sfox100/artist-radar |
| Star 数量 | 0 |
| 最近更新时间 | 2026-08-26 15:24:33 Asia/Shanghai |
| License | MIT |
| 技术架构 | 纯标准库 Python；多数据源联合；GitHub Actions 定时；状态文件差分 |
| 主要功能 | 盯艺人新演出公告、开售窗口、候补名单变化并推送 |
| 可借鉴模块 | **多源合并 + 去重 + 状态变化检测 + Actions 无服务器运行**；礼貌失败降级（单源失败不拖垮全体） |
| 潜在安全问题 | 依赖非官方/易变端点；Star 为 0、个人维护风险；需遵守各站 ToS；勿扩展成下单 |

#### 项目 B：concert-alert（Concert Scout）

| 字段 | 内容 |
|------|------|
| 项目名称 | concert-alert |
| GitHub 地址 | https://github.com/jazzy15j/concert-alert |
| Star 数量 | 0 |
| 最近更新时间 | 2026-11-03 06:06:08 Asia/Shanghai |
| License | API 未返回（仓库未见明确 SPDX） |
| 技术架构 | Python 3.12；Ticketmaster 等官方/公开源；`seen_events.json` 差分；邮件通知；GitHub Actions |
| 主要功能 | 每日新演出/关键字段变更提醒 |
| 可借鉴模块 | 「首轮建基线不通知 → 之后只报变更」；配置文件驱动的艺人/城市过滤 |
| 潜在安全问题 | 许可证不明 → **暂不引入代码**；API Key 存 Secrets，勿提交 |

#### 项目 C：concert-watcher

| 字段 | 内容 |
|------|------|
| 项目名称 | concert-watcher |
| GitHub 地址 | https://github.com/RyanConnell/concert-watcher |
| Star 数量 | 2 |
| 最近更新时间 | 2024-04-29 07:16:12 Asia/Shanghai |
| License | 未声明 |
| 技术架构 | Go；Ticketmaster API；Discord Webhook；可选 `--diff` |
| 主要功能 | 按艺人列表匹配附近演出并通知 |
| 可借鉴模块 | 官方 API 优先于页面抓取；差分去重通知 |
| 潜在安全问题 | 长期不更新；无许可证；仅作架构参考 |

**不采用**：依赖 Selenium 高频爬 Ticketmaster/StubHub 且夹杂购票搜索的个人脚本（如部分 `ConcertTicketsNotifier` 类仓库）——维护差、许可证不明，且易滑向违规自动化。

---

### 2.8 商品库存 / 状态监控项目

#### 项目 A：changedetection.io（强烈推荐作参考）

| 字段 | 内容 |
|------|------|
| 项目名称 | changedetection.io |
| GitHub 地址 | https://github.com/dgtlmoon/changedetection.io |
| Star 数量 | 35663 |
| 最近更新时间 | 2026-11-09 07:41:00 Asia/Shanghai |
| License | Apache-2.0 |
| 技术架构 | Python；网页变更检测；多通知后端；可自托管 |
| 主要功能 | 页面/价格/补货等变更告警（通用监控平台） |
| 可借鉴模块 | 变更检测流水线、通知插件化、限速与重试、可视化历史 Diff |
| 潜在安全问题 | 监控目标若需登录，凭证管理要隔离；对受保护站点爬取可能违规 |

#### 项目 B：shopify-monitor

| 字段 | 内容 |
|------|------|
| 项目名称 | shopify-monitor |
| GitHub 地址 | https://github.com/rp0201/shopify-monitor |
| Star 数量 | 0 |
| 最近更新时间 | 2025-11-01 00:47:09 Asia/Shanghai |
| License | MIT |
| 技术架构 | Python；读取 Shopify 公开 `products/[handle].json`；轮询对比 `inventory_quantity` |
| 主要功能 | 补货 / 售罄 / 数量变化日志 |
| 可借鉴模块 | 公开 JSON 端点 + 限速重试 + 状态对比（**仅当目标站点明确提供公开数据时**） |
| 潜在安全问题 | 并非所有店暴露库存字段；高频轮询可被封；Star 低 |

#### 项目 C：inventory_monitor

| 字段 | 内容 |
|------|------|
| 项目名称 | inventory_monitor |
| GitHub 地址 | https://github.com/jhiney/inventory_monitor |
| Star 数量 | 0 |
| 最近更新时间 | 2025-12-21 05:55:56 Asia/Shanghai |
| License | 未声明 |
| 技术架构 | Python；Shopify JSON 或正则；ntfy.sh 通知；本地状态 |
| 主要功能 | 新商品/有货提醒 |
| 可借鉴模块 | 「首轮只建基线」；ntfy 推送接线方式 |
| 潜在安全问题 | 无许可证；正则抓任意站易违规 |

#### 项目 D：priceprobe

| 字段 | 内容 |
|------|------|
| 项目名称 | priceprobe |
| GitHub 地址 | https://github.com/willylam2222-bot/priceprobe |
| Star 数量 | 3 |
| 最近更新时间 | 2026-07-21 05:34:28 Asia/Shanghai |
| License | MIT |
| 技术架构 | 零第三方依赖；页面抓取价格/库存；HTML 报告；Actions + Webhook |
| 主要功能 | 竞品价格与缺货/补货差分 |
| 可借鉴模块 | 纯标准库差分报告；Webhook 通知形态 |
| 潜在安全问题 | 通用页面抓取对 ToS 敏感；商业打包版与开源边界需分清 |

**明确不建议借鉴其对抗能力的项目**：宣传「proxies to bypass anti bot」「captcha_solvers」「stealth」的库存监控（例如部分 Amazon 补货 checker 文档结构）。本项目 **禁止** 引入验证码求解、指纹伪装、代理池撞风控。

---

## 3. 特别调研：是否存在合法的大麦「公开信息」监控开源项目？

### 3.1 结论（直接回答）

| 问题 | 结论 |
|------|------|
| 是否存在大麦官方开源监控 SDK/API 封装？ | **未发现** |
| 是否存在「只读公开开售/演出信息、许可证清晰、社区广泛认可」的专用监控项目？ | **基本没有**；最接近的也是个人小仓或与库存 Cookie 混杂 |
| GitHub 上大麦相关主流仓库是什么？ | **抢票 / App 自动化 / 逆向 / 多账号** 居多 → **一律不建议使用** |

### 3.2 相关仓库评估

#### A. jianrongfeng/damai-notify（方向接近，质量不足）

| 字段 | 内容 |
|------|------|
| 项目名称 | damai-notify |
| GitHub 地址 | https://github.com/jianrongfeng/damai-notify |
| Star 数量 | 2 |
| 最近更新时间 | 2026-10-13 06:31:19 Asia/Shanghai（`updated_at` 仍停在 2023，活跃度存疑） |
| License | **未声明** |
| 技术架构 | Java / Maven；解析演出详情 HTML；SMTP 邮件 |
| 主要功能 | 检测开票相关信息并邮件提醒 |
| 可借鉴模块 | 「详情页可读信息 → 判断是否开票 → 邮件」的产品思路（**概念级**） |
| 潜在安全问题 | 无许可证不可复制代码；HTML 结构易变；可能触发站点封禁 |

**评级**：可作为「开票提醒」产品形态参考；**不可依赖、不可拷贝**。

#### B. zemojix-0305/ticket-radar（监控方向，含敏感实现面）

| 字段 | 内容 |
|------|------|
| 项目名称 | ticket-radar |
| GitHub 地址 | https://github.com/zemojix-0305/ticket-radar |
| Star 数量 | 9 |
| 最近更新时间 | 2026-11-01 15:53:35 Asia/Shanghai |
| License | MIT |
| 技术架构 | Python 常驻引擎 + 小程序；SQLite；多平台适配器；多通道推送 |
| 主要功能 | 余票/状态监控并推送；文档称用户自行去官方渠道购买；宣称不破解验证码 |
| 可借鉴模块 | **仅概念**：三态库存模型、首轮基线、平台级限流队列、通知通道抽象 |
| 潜在安全问题 | 大麦逐票档库存依赖用户 Cookie / 非公开接口形态；文档亦提及风控与 App 签名边界——**本项目不得复制其请求签名、Cookie 抓取教程或库存探测实现** |

**评级**：架构「监控 + 通知」可参考；**实现层不引入**。

#### C. 明确不建议使用的大麦相关项目（抢票 / 对抗类）

| 项目 | 地址 | Stars | License | 为何不建议 |
|------|------|------:|---------|------------|
| HaTickets | https://github.com/currycan/HaTickets | 559 | Apache-2.0 | 自述「大麦网抢票自动化」Mobile U2 / Desktop Tauri |
| tickets | https://github.com/shiyutim/tickets | 3554 | MIT | 自述「调用接口的抢票软件」；含自动下单/重试/多账号 Cookie |
| damaiqiangpiao/damai | https://github.com/damaiqiangpiao/damai | 556 | 未声明 | 抢票技术社区；Frida/Root 隐藏/风控滑块等 |
| Heinriciro/damai-ticket-analysis | https://github.com/Heinriciro/damai-ticket-analysis | 1 | Apache-2.0 | Frida + 抓包分析购票细节（逆向向） |
| ximplez/TicketMonitoring | https://github.com/ximplez/TicketMonitoring | 0 | 未声明 | 「回流票监控」；来源/许可不清，易与违规刷票场景绑定 |

> 以上仓库 **禁止** 作为依赖、禁止复制代码、禁止在本仓库文档中提供其绕过/下单步骤。

### 3.3 对本项目的合规数据源建议（调研级，非实现）

在 **不逆向、不绕过风控** 前提下，后续阶段应优先：

1. **用户粘贴的官方活动 URL / 项目 ID**（用户已知公开信息）；
2. **用户手动录入的开售时间**（日历提醒，零抓取）；
3. 若存在 **平台官方、文档化、允许的公开接口或 RSS/公告**，再评估只读接入；
4. 可选：用系统默认浏览器打开官方页，由用户人工购票；
5. 避免：mtop 私有签名复刻、App 设备指纹、验证码服务、队列插队、多账号。

---

## 4. 推荐技术栈（本项目）

| 层级 | 推荐 | 许可证要点 | 用途 |
|------|------|------------|------|
| 语言 | Python 3.13 | — | 与现环境一致 |
| GUI | **PySide6** | LGPL/GPL 双许可需合规 | 主窗口、任务面板、托盘 |
| 调度 | **APScheduler** | MIT | 开售提醒、低频检查 |
| 存储 | **sqlite3**（必要时 SQLAlchemy） | PSF / MIT | 任务、快照、通知日志 |
| 浏览器 | **Playwright**（可选）或系统默认浏览器 | Apache-2.0 | 仅打开官方页 / 辅助核对 |
| 桌面通知 | **desktop-notifier** 或 **plyer**；托盘提示兜底 | MIT | 本地提醒 |
| 远程通知（可选） | **ntfy** / 邮件 / Webhook | Apache-2.0 等 | 离开桌面时的提醒 |
| 打包 | **PyInstaller** | GPL-2.0-or-later + Bootloader Exception | Windows 等分发 |
| 配置 | PyYAML | MIT | `config/settings.yaml` |
| 监控模式借鉴 | changedetection.io（思想）、artist-radar / concert-alert（差分与基线） | Apache-2.0 / MIT / 视仓库 | 状态机与通知，不抄站点私有协议 |

**明确不进入技术栈**：验证码打码平台、反检测 stealth 插件、代理池用于撞风控、Appium/U2 大麦 App 抢购脚本、任何「自动提交订单」库。

---

## 5. 不建议使用的项目 / 类别（汇总）

1. **一切以「抢票 / qiangpiao / 自动下单 / 秒杀」为主述的仓库**（含 HaTickets、shiyutim/tickets、damaiqiangpiao/damai 等）。
2. **提供验证码绕过、排队插队、设备指纹伪造、Frida Hook 购票签名** 的教程仓与工具链。
3. **依赖未声明许可证** 的监控小仓（可作思路观察，不可拷贝代码）——如部分 concert/inventory 个人脚本、`damai-notify`。
4. **库存监控中带 anti-bot bypass / captcha solver** 的实现（即使目标是电商补货）。
5. **多账号 Cookie 池 + 并发下单** 类工作台功能（即使某仓同时带「余票提醒」）。

---

## 6. 对本仓库下一阶段的启示（仍不实现）

1. 保持 README 中的 **monitor / reminder** 边界声明。
2. 模块划分可继续按：`scheduler`（提醒） / `monitor`（公开状态差分） / `notifier` / `database` / `gui`；**不要**增加 `checkout` / `captcha` / `account_pool`。
3. Playwright 若引入，API 表面应叫 `open_official_page` 一类，避免 `grab` / `buy` 命名污染。
4. 大麦数据接入前先做 **ToS / 机器人条款** 核对；无合规来源则仅支持「用户手动开售时间提醒」。

---

## 7. 覆盖统计

| 类别 | 详细记录的项目数 |
|------|------------------|
| Playwright | 1 |
| PySide6 | 1 |
| APScheduler | 1 |
| SQLite 相关 | 3 |
| PyInstaller | 1 |
| 桌面/推送通知 | 4（plyer、notify-py、desktop-notifier、ntfy） |
| 演出信息监控 | 3 |
| 库存/变更监控 | 4 |
| 大麦专项（含不建议） | 6 |
| **合计（去重后约）** | **24** |

---

## 8. 参考抓取方式

```text
GET https://api.github.com/repos/{owner}/{repo}
字段: stargazers_count, pushed_at, license.spdx_id, description, archived
```

本报告不包含任何抢票 PoC、请求签名细节或可复现的绕过步骤。
