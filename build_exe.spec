# -*- mode: python ; coding: utf-8 -*-
# build_exe.spec  ─  PyInstaller spec for "Message Sender"

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# pystray は backend を動的 import するため全サブモジュールを同梱
hidden_imports = (
    collect_submodules("pystray")
    + collect_submodules("PIL")
    + collect_submodules("openai")
    + [
        "PIL._tkinter_finder",
        "tkinter",
        "tkinter.ttk",
        "email.mime.text",
        "email.mime.multipart",
        "email.header",
        "email.utils",
        "dotenv",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # .env・CSV など実行時に読み込むファイルをそのまま同梱
        (".env",         "."),
        ("users.csv",    "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MessageSender",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # ← GUI アプリなのでコンソール非表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",      # アイコンファイルがあればコメントを外す
)
