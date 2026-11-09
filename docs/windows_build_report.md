# Windows 构建报告（v0.11.0）

记录日期：2026-11-09（UTC）。本文件在 **GitHub Actions `windows-latest` 构建成功之后**追加，不在标签 `v0.11.0` 所指向的树里。标签指向的提交才是被打包的源码。

产品边界：开售监控 / 提醒 / 人工打开官方页。本构建不包含自动购票。

本报告只描述 Windows 运行器上的 PyInstaller onedir 结果。它不是 Linux 上 pytest 的结论，也没有在 Linux 上启动这个 EXE。

## 结论

**成功。** 推送附注标签 `v0.11.0` 触发了工作流 `Windows Build`。作业 `Build EXE (windows-latest)` 结论为 `success`。产物 `DamaiTicketAssistant-windows` 已上传，并用 `gh run download` 在本机解开，确认其中有 `DamaiTicketAssistant.exe`。

没有改打包脚本，也没有第二次运行。

## 仓库落点

来源是完整 git bundle（tip `cc18a7d`）。`git bundle verify` 显示历史完整。取入 `refs/heads/master` 后改名为 `main`。

远程当时只有占位提交 `71a600e89c787f3435b094c528a595a6b685c47a`（`Initial commit`，仅一行 README `# Damai-Concert`）。普通推送被拒绝（non-fast-forward）。随后用 `--force-with-lease=refs/heads/main:71a600e89c787f3435b094c528a595a6b685c47a` 只覆盖该占位提交。

| 项 | 值 |
|----|----|
| 仓库 | https://github.com/romantic1678/Damai-Concert |
| 默认分支 | `main` |
| `main` / 构建提交 | `cc18a7d8d53dd73634b1fb7ca7ba896376839429` |
| 附注标签 | `v0.11.0` |
| 标签对象 | `129d77dadce03ec92193ddca32b1751ffe1588ff` |
| 标签目标 | `cc18a7d8d53dd73634b1fb7ca7ba896376839429` |
| 标签说明 | `Damai Ticket Assistant 0.11.0` |
| 工作流文件 | `.github/workflows/windows-build.yml`（已在 `main` 上，blob `f0abc2148c625968f3984e07ba2d59c72cc628c8`） |
| 工作流 | `Windows Build`，id `411942560`，状态 active |

`main` 上的 11 个提交（新到旧）：

| SHA | 说明 |
|-----|------|
| `cc18a7d8d53dd73634b1fb7ca7ba896376839429` | build: phase 11 Windows packaging scripts and GitHub Actions workflow |
| `8fbced874949a1c1333832b9c719f0834d93f88d` | test+docs: phase 10 test and security reports |
| `76d0bd67645b9912989ad16f4a4ca05d397ced28` | feat: phase 9 Chinese PySide6 desktop GUI |
| `f27295aabb525e1dd13a3aebcae2a2a4e45071d2` | feat: phase 8 Playwright browser assist with human takeover |
| `2a2eb1592e1fb117449233e097c9aca83689cb95` | feat: phase 7 multi-channel notifications with dedupe |
| `4a6c4dd1521a2e4af28f07c8ff965bd9d1d94cda` | feat: phase 6 countdown, reminders, and public status monitor |
| `07e8bffab41eb193df08888038f6735ad6a66317` | feat: phase 5 concert task CRUD, validation, search/sort |
| `345e277c65b3ae5ecb7efbb9ea6d03e1648391aa` | feat: phase 4 foundation — config, logging, sqlite, models, tasks, tests |
| `0e7d2adb0c01e76fc15cce4e587e3a7fc957e9f6` | docs: add architecture, database design, and development plan (phase 3) |
| `7bd7f4d54bf45dc7abab4029d75693c5f8e8163d` | docs: add open-source research report (phase 2) |
| `92389595b8b0c88af50288405e1f6ced4ce6d363` | Initial scaffold: Damai Ticket Assistant (monitor/reminder) |

归档包 `damai-ticket-assistant-cc18a7d.tar.gz` 没有使用。

## 如何触发

标签推送已经匹配工作流里的 `push.tags: v*`，运行随即出现，因此没有再调用 `workflow_dispatch`。

```text
gh workflow list
# Windows Build    active    411942560

# 实际触发：git push origin v0.11.0
# 事件：push
# 头提交：cc18a7d8d53dd73634b1fb7ca7ba896376839429
# 显示标题：build: phase 11 Windows packaging scripts and GitHub Actions workflow
```

## Actions 运行

| 项 | 值 |
|----|----|
| 运行 | https://github.com/romantic1678/Damai-Concert/actions/runs/42600557265 |
| 作业 | https://github.com/romantic1678/Damai-Concert/actions/runs/42600557265/job/129103661213 |
| 运行 id | `42600557265` |
| 作业 id | `129103661213` |
| 作业名 | `Build EXE (windows-latest)` |
| 事件 | `push`（标签 `v0.11.0`） |
| 结论 | `success` |
| 运行创建 | 2026-11-09T10:23:43Z |
| 作业开始 | 2026-11-09T10:23:48Z |
| 作业结束 | 2026-11-09T10:30:56Z |
| 运行更新 | 2026-11-09T10:30:57Z |
| 作业耗时 | 7 分 8 秒（`gh run watch` 显示 `7m8s`） |
| 运行器 | `windows-latest` |
| 镜像 | `windows-2025-vs2026`，版本 `20261103.298.1` |
| 系统 | Microsoft Windows Server 2025 Datacenter `10.0.26100` |
| Python | CPython 3.13.17（`actions/setup-python@v5`） |

步骤（全部 success）：

| 步骤 | 开始 (UTC) | 结束 (UTC) |
|------|------------|------------|
| Set up job | 10:23:49 | 10:23:50 |
| Checkout | 10:23:50 | 10:23:56 |
| Set up Python 3.13 | 10:23:56 | 10:24:00 |
| Build with PowerShell | 10:24:00 | 10:29:52 |
| Verify artifact exists | 10:29:52 | 10:29:53 |
| Upload Windows dist | 10:29:53 | 10:30:41 |
| Post Set up Python 3.13 | 10:30:41 | 10:30:53 |
| Post Checkout | 10:30:53 | 10:30:54 |
| Complete job | 10:30:54 | 10:30:54 |

构建日志中的版本：PyInstaller 6.22.3，contrib hooks 2026.9，PySide6 6.12.0，playwright 1.64.1。Playwright 下载的是 Chrome for Testing `156.0.8078.4`（chromium v1248，win64）。

脚本打印：

```text
=== Build OK ===
EXE:  D:\a\Damai-Concert\Damai-Concert\dist\DamaiTicketAssistant\DamaiTicketAssistant.exe (5.49 MB)
Dist: D:\a\Damai-Concert\Damai-Concert\dist\DamaiTicketAssistant (1506.99 MB total)
Browsers: D:\a\Damai-Concert\Damai-Concert\dist\DamaiTicketAssistant\ms-playwright (717.95 MB)
```

校验步骤读到了 `dist/DamaiTicketAssistant/DamaiTicketAssistant.exe` 和 `BUILD_OK.txt`。

## 产物

| 项 | 值 |
|----|----|
| 名称 | `DamaiTicketAssistant-windows` |
| Artifact id | `13666465294` |
| 压缩大小 | `655168185` 字节（约 624.6 MiB） |
| 创建 | 2026-11-09T10:30:40Z |
| 过期 | 2026-11-23T10:29:54Z（`expired: false`，retention 14 天） |
| 上传路径 | `dist/DamaiTicketAssistant`（`if-no-files-found: error`） |

下载命令（已成功）：

```text
gh run download 42600557265 --repo romantic1678/Damai-Concert \
  --name DamaiTicketAssistant-windows --dir /tmp/dta-win
```

解开后的顶层：

- `DamaiTicketAssistant.exe`
- `BUILD_OK.txt`
- `_internal/`（本机 `du`：798M）
- `ms-playwright/`（本机 `du`：720M；含 `chromium-1248/chrome-win64`、`chromium_headless_shell-1248`、`ffmpeg-1013`、`winldd-1007`）

合计 5396 个文件，目录约 1.5G，与日志里的 `dist_mb=1506.99` 一致。

`BUILD_OK.txt` 原文：

```text
DamaiTicketAssistant Windows build OK
exe_mb=5.49
dist_mb=1506.99
browsers_mb=717.95
generated=2026-11-09T10:29:52.2552850+00:00
```

EXE 事实（下载后在 Linux 上只做了类型识别，没有运行）：

| 项 | 值 |
|----|----|
| 路径 | `DamaiTicketAssistant.exe`（产物根目录，onedir 引导程序） |
| 大小 | `5753873` 字节（5.49 MB） |
| `file` | `PE32+ executable (GUI) x86-64, for MS Windows, 7 sections` |

5.49 MB 只是 PyInstaller 引导程序。Qt / Python 运行时在 `_internal`，Chromium 在 `ms-playwright`。要在 Windows 上使用，需要整个解压目录，而不是单独拷贝这个 EXE。

## 修复

无。第一次标签构建即成功，没有为打包提交后续修复。

## 遗留（未阻断成功）

1. **PyInstaller 警告**：`Failed to collect submodules for 'PySide6.scripts.deploy_lib'`，原因是 `ModuleNotFoundError: No module named 'project_lib'`。作业仍然成功。校验列表里仍能看到 `_internal\PySide6\scripts\deploy_lib\` 被拷入。这是 PySide6 自带的部署辅助模块，不是应用入口。本次未改 spec。
2. **Actions 注解**：`Node.js 20 is deprecated`。`actions/checkout@v4`、`actions/setup-python@v5`、`actions/upload-artifact@v4` 仍声明 Node 20，被强制在 Node 24 上执行。构建未失败。
3. **体积**：onedir 加 PySide6 加 Playwright Chromium 后，压缩包约 625 MiB，解开约 1.5 GiB。这是当前打包方式的结果，不是失败。
4. **未在 Windows 桌面点开 GUI**。成功依据是运行器上的校验步骤、产物上传，以及下载后的 `file` 识别。Linux 不能执行这个 PE，因此这里没有“已启动应用”的结论。
5. 首次运行日志有 `pip cache is not found`。Python 步骤仍成功，缓存已在作业末尾写入。
