# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('frontend/dist', 'frontend/dist'),
        ('backend', 'backend'),
        ('data', 'data'),
    ],
    hiddenimports=[
        'flask', 'openpyxl', 'pymysql', 'waitress', 'gevent',
        'cryptography', 'requests', 'dotenv', 'webview',
        'webview.platforms.edgechromium',
        'backend.ai_client', 'backend.database', 'backend.auth',
        'backend.export', 'backend.import_data', 'backend.audit',
        '_cffi_backend', 'cffi', 'cffi.api',
        'pythonnet', 'clr_loader', 'clr_loader.ffi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dynamic_registry',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
