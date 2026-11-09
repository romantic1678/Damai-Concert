# Damai Ticket Assistant — 安全审查报告（第十阶段）

> **审查时间**：2026-11-09 18:03–18:04 Asia/Shanghai  
> **版本**：0.10.0  
> **范围**：`app/`、`tests/`、`config/`、`README.md`、`.gitignore`（不含 `.venv`、调研文档中的第三方项目描述）  
> **方法**：`rg` 关键词扫描 + 人工阅读关键模块；对照产品边界清单。

---

## 1. 产品边界声明（已确认存在）

| 声明位置 | 内容摘要 |
|----------|----------|
| `README.md` | Does NOT：auto-purchase、bypass anti-bot、multi-account、抢票/下单 |
| `app/browser/assist.py` 模块 docstring | NO captcha solve/bypass、queue jump、stealth/fingerprint、auto payment、不收集凭据 |
| `config/settings.example.yaml` | `mode: monitor_reminder`；注释禁止 purchase/checkout |
| `app/main.py` | CLI 描述强调不购票、不绕过风控 |
| `app/config.py` | 拒绝非 `monitor_reminder` 的 `app.mode` |

---

## 2. 检查清单与证据

### 2.1 明文密码

| 结论 | **未发现生产代码存储或硬编码明文密码** |
|------|----------------------------------------|
| 扫描 | `password` / `passwd` 命中主要为：禁止声明、测试用 login 夹具 `<input type="password">`、`test_manual_login_page_does_not_scrape_password` |
| 证据 | `tests/fixtures/browser/login.html` 仅有空表单控件；`tests/test_browser.py` 断言存在 password 输入框但**从不** `fill`；`BrowserAssist` 无 credentials API |
| 风险 | 低：用户在 Playwright 窗口自行输入时，会话仅在用户本机浏览器配置中（当前默认不启用 persistent profile） |

### 2.2 Cookie / storage_state 泄露

| 结论 | **未发现 Cookie 落盘或日志打印 Cookie** |
|------|----------------------------------------|
| 扫描 | 无 `storage_state`、`cookies.json`、日志格式化 Cookie 的实现 |
| 架构/库表 | `browser_sessions` 明确禁止 cookies 列（见 `docs/database_design.md`） |
| 残留 | 若未来启用 `user_data_dir` 持久化上下文，需文档警示会话文件权限（当前 `lifecycle` 传入 `user_data_dir=None`） |

### 2.3 API Key / Secret

| 结论 | **仓库示例配置与源码中未发现 API Key / Bearer / AWS 密钥形态** |
|------|--------------------------------------------------------------|
| 扫描 | `sk-`、`AKIA`、`Bearer `、`2captcha`、`anticaptcha`：**无命中** |
| `.gitignore` | 忽略 `config/settings.yaml`、`.env`、`*.db`、`data/*`、`*.log` |
| `settings.example.yaml` | 无密钥字段；注释 “Do not commit secrets” |

### 2.4 自动支付 / 下单

| 结论 | **不存在自动支付或下单代码路径** |
|------|--------------------------------|
| 扫描 | `place_order` / `create_order` / `auto_buy` / `checkout` 业务实现：**无**；`checkout` 仅出现在禁止说明与模式注释 |
| GUI | 打开官方页后提示「不会自动下单」 |

### 2.5 未经授权内部接口

| 结论 | **应用未实现大麦 mtop 签名/私有 API 客户端** |
|------|---------------------------------------------|
| 监控 | `RejectNetworkFetcher` 默认拒绝网络；fixture 仅读本地文件 |
| 浏览器 | 仅 `goto` 用户提供的白名单 URL 或 localhost mock |
| 调研文档 | `docs/research_report.md` 提及第三方抢票仓仅作「不建议」清单，**未引入其代码** |

### 2.6 验证码破解

| 结论 | **无验证码求解实现** |
|------|---------------------|
| 行为 | `heuristics.needs_human_verification` 仅检测「验证码/滑块/排队」等文案并触发 **人工接管通知** |
| 明示 | `assist.py`：`NO captcha solve / bypass` |
| 扫描 | `solve_captcha` / `2captcha` / `anticaptcha`：**无命中** |

### 2.7 绕过排队 / 风控 / stealth

| 结论 | **无 stealth、指纹伪造、插队逻辑** |
|------|-----------------------------------|
| 证据 | Playwright 启动注释 “No stealth flags — intentionally stock Chromium”；无 `undetected` / `stealth_async` / `libmtguard` / `frida` |
| 排队 | 仅作为「需要用户操作」的启发式信号，不跳过队列 |

---

## 3. 本阶段发现与处置

| ID | 发现 | 级别 | 处置 |
|----|------|------|------|
| S1 | `notification_logs` 对不存在的 `task_id` 插入触发 SQLite FK 错误（进程不崩，但 ERROR 日志） | 中 | **已修复**：插入前校验 `concert_tasks`；缺失则写 `NULL`（`app/notify/base.py`）+ 回归测试 |
| S2 | 测试夹具含 password 输入框 | 信息 | 可接受：用于证明**不**自动填表；无真实口令 |
| S3 | 默认监控 fetcher 拒绝一切网络 | 正面 | 降低误连真实站点风险 |

---

## 4. 残留风险（可接受 / 后续）

1. **用户人工登录**：官方页登录态由用户自行管理；勿在日志中增加页面 HTML 全量 dump（当前无）。  
2. **白名单绕过**：仅允许配置中的域名 + 本地 mock；用户若自行改宽 `url_allowlist` 需自负风险。  
3. **桌面通知依赖 plyer**：无密钥问题；失败已吞掉。  
4. **调研报告中的外部链接**：文档引用抢票类仓库名称仅作警示，部署物不含其代码。

---

## 5. 结论

在当前代码库范围内：**未发现明文密码存储、Cookie/API Key 泄露、自动支付、验证码破解、排队/风控绕过或 stealth 实现**。  
关键问题 S1 已在本阶段修复并通过全量 **64** 项 Pytest。产品定位仍严格为 **开售监控 / 提醒 / 人工打开官方页**。
