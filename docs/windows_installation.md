# Windows 安装与构建说明（Damai Ticket Assistant）

> **重要**：当前日常研发环境是 **Debian Linux**。  
> **不能**在 Linux 上打包出可在 Windows 直接运行的 EXE，也不要把 Linux 产物当成 Windows 安装包。  
> Windows EXE 应由 **GitHub Actions `windows-latest` 运行器**（或真实 Windows 机器）执行 `scripts/build_windows.ps1` 生成。

产品边界不变：**仅开售监控 / 提醒 / 人工打开官方页**，不自动购票、不破解验证码、不绕过风控。

---

## 1. 构建产物如何产生

### 1.1 GitHub Actions（推荐）

工作流文件：`.github/workflows/windows-build.yml`

触发方式：

- 手动：`Actions` → `Windows Build` → `Run workflow`（`workflow_dispatch`）
- 打标签：推送匹配 `v*` 的 tag（例如 `v0.11.0`）

流程概要：

1. `actions/checkout`
2. `actions/setup-python` → Python **3.13**
3. 运行 `scripts/build_windows.ps1`  
   - 创建 `.venv-win`  
   - `pip install -r requirements.txt` + PyInstaller  
   - `python -m playwright install chromium`（浏览器落到 `build/ms-playwright`）  
   - `PyInstaller DamaiTicketAssistant.spec`（**onedir**）  
   - 将 `ms-playwright` 复制到 `dist/DamaiTicketAssistant/ms-playwright`  
   - 校验 `DamaiTicketAssistant.exe` 存在并写出 `BUILD_OK.txt`
4. `actions/upload-artifact` 上传整个 `dist/DamaiTicketAssistant` 目录

若仓库尚未完成 GitHub 授权 / 未能推送工作流，则 **不会**产生 EXE——这是预期状态，不是脚本假装成功。

### 1.2 本机 Windows（可选）

在 Windows 上安装 Python 3.13 后：

```powershell
cd damai-ticket-assistant
pwsh -File .\scripts\build_windows.ps1
```

产物目录：`dist\DamaiTicketAssistant\`

---

## 2. 下载与运行

1. 打开 GitHub 仓库 → **Actions** → 选中成功的 `Windows Build` 运行记录  
2. 下载 Artifact：`DamaiTicketAssistant-windows`  
3. 解压到任意目录（路径避免极端权限限制）  
4. 双击 `DamaiTicketAssistant.exe`（无参数时默认启动中文 GUI）

首次启动会在用户可写目录创建数据文件（见下一节）。

---

## 3. 数据目录（冻结运行时）

| 用途 | 路径 |
|------|------|
| 配置 / SQLite / 日志 | `%LOCALAPPDATA%\DamaiTicketAssistant\` |
| 默认数据库 | `%LOCALAPPDATA%\DamaiTicketAssistant\data\app.db` |
| 日志 | `%LOCALAPPDATA%\DamaiTicketAssistant\data\logs\app.log` |
| 用户配置 | `%LOCALAPPDATA%\DamaiTicketAssistant\config\settings.yaml`（若不存在则从包内 `settings.example.yaml` 复制） |

源码运行（未打包）仍使用仓库下的 `data/` 与 `config/`。

实现见 `app/paths.py`（`sys.frozen` / `sys._MEIPASS`）。

---

## 4. Playwright 浏览器路径

打包策略（务实）：

- PyInstaller **onedir** 打包应用与 PySide6 / playwright **驱动**  
- Chromium 由构建脚本安装并复制到 **`dist/DamaiTicketAssistant/ms-playwright`**  
- 运行时优先：`PLAYWRIGHT_BROWSERS_PATH` → EXE 旁 `ms-playwright` → `%LOCALAPPDATA%\DamaiTicketAssistant\ms-playwright`

若 Artifact 体积过大导致 Actions 上传失败，可改为仅上传 EXE+依赖，并在用户机器首次运行时执行：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\DamaiTicketAssistant\ms-playwright"
python -m playwright install chromium
```

（冻结包内需自带 `playwright` CLI 或文档指导用户安装官方浏览器组件。）

---

## 5. 限制与注意

1. **Linux 构建机无法产出可用 Windows EXE。**  
2. 未完成 GitHub 登录/推送时，无法声称「已发布安装包」。  
3. 杀毒软件可能误报 PyInstaller 程序，需自行添加信任。  
4. GUI 为窗口子系统（`console=False`）；调试可临时改 spec 开控制台。  
5. 仍不支持自动购票；打开大麦页面后请用户手动操作。

---

## 6. 故障排查

| 现象 | 处理 |
|------|------|
| Actions 失败：缺少 EXE | 查看 `build_windows.ps1` 日志；确认 `DamaiTicketAssistant.spec` 与 `run_app.py` 在仓库根目录 |
| 启动闪退 | 检查 `%LOCALAPPDATA%\DamaiTicketAssistant\data\logs\`；确认 VC++ 运行库齐全 |
| 浏览器打不开 | 确认 `ms-playwright` 目录存在；或设置 `PLAYWRIGHT_BROWSERS_PATH` 后重装 Chromium |
| 配置丢失 | 勿删除 `%LOCALAPPDATA%\DamaiTicketAssistant`；可从 `settings.example.yaml` 重建 |
| Artifact 太大 | 从产物中剔除 browsers，改为 LocalAppData 安装（见第 4 节） |

---

## 7. 相关文件

- `scripts/build_windows.ps1`  
- `.github/workflows/windows-build.yml`  
- `DamaiTicketAssistant.spec`  
- `run_app.py`  
- `app/paths.py`
