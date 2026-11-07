# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec：零依赖后端（Electron 桌面壳专用）
#
# 产物：dist/backend_server/backend_server.exe（onedir，非单文件）
#   为什么 onedir 而不是 onefile：
#     * onefile 每次启动要解压整个运行时到 %TEMP%，冷启动慢 2-5 秒；
#     * 杀软对单文件自解压样本误报率显著更高；
#     * onedir 目录整体作为 electron-builder 的 extraResources 打进安装包，
#       用户无感知，升级时随安装目录整体替换（数据在 userData，不受影响）。
#
# 与 desktop.spec（pywebview 单文件方案）互不影响：那是遗留旧方案，
# Electron 链路只用本 spec。

a = Analysis(
    ['backend_server.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # backend 纯源码：main.ts 的 mac 镜像逻辑按目录整体拷贝 backend/
        ('backend', 'backend'),
        # 前端构建产物：app.py frozen 态的 FRONTEND_DIST 指向 <_MEIPASS>/static
        ('frontend/dist', 'static'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'waitress',
        'flask',
        'flask_cors',
        'openpyxl',
        'cryptography',
        'backend.db_adapter',
        'backend.row_store',
        'backend.config',
        'backend.uuid7',
        'backend.vecsearch',
        'backend.ai_client',
        'backend.db_crypto',
        'backend.drsync',
        'backend.drsync.crypto',
        'backend.drsync.events',
        'backend.drsync.node',
    ],
    excludes=[
        # 桌面包里用不到的重依赖：减小体积、降低误报
        'locust',
        'gevent',
        'pywebview',
        'tkinter',
        'matplotlib',
        'numpy',
        'pytest',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir：二进制放同级目录，由 COLLECT 收集
    name='backend_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX 是误报重灾区，零依赖包首要目标是"杀软不叫"
    console=False,           # GUI 进程：不弹黑窗；日志走 stdout 被 Electron 捕获
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='backend_server',
)
