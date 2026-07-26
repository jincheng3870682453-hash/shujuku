# -*- coding: utf-8 -*-
"""
build.py - PyInstaller 打包脚本
使用方式: python build.py
生成的可执行文件位于 dist/ 目录
"""
import PyInstaller.__main__
import os
import sys

# 确保在项目根目录下运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── 根据入口文件决定打包 desktop.py 还是 run.py ──
# 如果有 desktop.py 且安装了 pywebview，则打包桌面版；否则打包浏览器版
entry_script = 'run.py'
try:
    import webview
    if os.path.exists('desktop.py'):
        entry_script = 'desktop.py'
        print('📦 检测到 pywebview，将打包桌面版 (desktop.py)')
    else:
        print('📦 打包浏览器版 (run.py)')
except ImportError:
    print('📦 未安装 pywebview，将打包浏览器版 (run.py)')

# ── 收集数据文件 ──
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# ── 隐藏导入（确保打包后关键模块不丢失） ──
hidden_imports = [
    'flask',
    'flask.json',
    'sqlite3',
    'openpyxl',
    'hashlib',
    'secrets',
    'json',
    'atexit',
    'threading',
    'webbrowser',
    'functools',
    'datetime',
    'io',
    'tempfile',
]

# pywebview 相关隐藏导入（即使当前环境未安装，也写进列表以防漏）
if entry_script == 'desktop.py':
    hidden_imports.extend([
        'pywebview',
        'pywebview.platforms.winforms',
        'webview',
    ])

# ── 执行 PyInstaller ──
PyInstaller.__main__.run([
    '--name=DynamicRegistry',
    '--onedir',  # 使用 onedir 模式，启动更快
    '--windowed',  # 不显示控制台窗口（桌面应用）
    f'--add-data=templates{os.pathsep}templates',
    f'--add-data=static{os.pathsep}static',
    *[f'--hidden-import={m}' for m in hidden_imports],
    '--clean',
    '--noconfirm',
    entry_script,
])