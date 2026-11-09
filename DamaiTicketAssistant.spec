# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Damai Ticket Assistant (Windows onedir).
# Monitor / reminder only — no purchase automation.
#
# Build on windows-latest via scripts/build_windows.ps1 — do not expect a
# Linux-built EXE to run on Windows.

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

pyside_datas, pyside_binaries, pyside_hidden = collect_all("PySide6")
# Playwright Python package (driver); browsers are shipped beside dist via build script.
try:
    pw_datas, pw_binaries, pw_hidden = collect_all("playwright")
except Exception:
    pw_datas, pw_binaries, pw_hidden = [], [], []

hiddenimports = sorted(
    set(
        pyside_hidden
        + pw_hidden
        + collect_submodules("app")
        + [
            "apscheduler.schedulers.background",
            "apscheduler.triggers.date",
            "apscheduler.triggers.interval",
            "yaml",
            "plyer.platforms.win.notification",
            "plyer.platforms.linux.notification",
        ]
    )
)

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=pyside_binaries + pw_binaries,
    datas=pyside_datas
    + pw_datas
    + [
        ("config/settings.example.yaml", "config"),
        ("README.md", "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DamaiTicketAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI subsystem
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DamaiTicketAssistant",
)
