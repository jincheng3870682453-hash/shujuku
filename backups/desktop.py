# -*- coding: utf-8 -*-
"""
desktop.py - pywebview 桌面化封装
启动逻辑：后台线程运行 Flask，主线程创建 webview 窗口
"""
import sys
import os
import threading
import atexit
import signal
import traceback
from datetime import datetime

# 确保项目根目录在 sys.path 中，方便 pyinstaller 打包后也能找到模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 强制输出日志到文件（用于 PyInstaller --windowed 无控制台场景下捕获错误）
sys.stderr = open('flask_error.log', 'w', encoding='utf-8')
sys.stdout = open('flask_out.log', 'w', encoding='utf-8')

from app import app, init_db

# ──────────────────────── Flask 后台线程 ────────────────────────

_flask_thread = None
_flask_started = threading.Event()

def start_flask():
    """在后台线程中启动 Flask 服务器"""
    global _flask_thread
    init_db()
    # 注意：不使用 webbrowser.open，因为桌面壳已经提供窗口
    _flask_started.set()
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)


def stop_flask():
    """优雅停止 Flask（通过 atexit 注册）"""
    import requests
    try:
        # 发送一个关闭请求（Flask 开发服务器没有内置关闭端点，这里仅做清理）
        pass
    except Exception:
        pass


# ──────────────────────── 主入口 ────────────────────────

def main():
    # 启动 Flask 后台线程
    flask_thread = threading.Thread(target=start_flask, daemon=True, name='flask-server')
    flask_thread.start()

    # 等待 Flask 启动完成
    _flask_started.wait(timeout=10)

    # 注册退出清理
    atexit.register(stop_flask)

    # 启动 pywebview 桌面窗口
    try:
        import webview
    except ImportError:
        print("错误: 未安装 pywebview，请执行: pip install pywebview")
        print("回退到浏览器模式…")
        import webbrowser
        import time
        time.sleep(1.5)
        webbrowser.open('http://127.0.0.1:5001')
        # 保持主线程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n已退出")
        return

    # 创建桌面窗口
    window = webview.create_window(
        title='动态数据登记系统',
        url='http://127.0.0.1:5001',
        width=1200,
        height=800,
        min_size=(900, 600),
        confirm_close=False,  # 直接关闭，无需确认
    )

    # 启动 webview 事件循环（阻塞直到窗口关闭）
    webview.start()

    # 窗口关闭后，清理进程
    print("窗口已关闭，正在退出…")
    os._exit(0)


if __name__ == '__main__':
    main()