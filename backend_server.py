# -*- coding: utf-8 -*-
"""
PyInstaller 打包态后端入口（零依赖安装包专用）
================================================

与 app.py 的关系：
  * app.py 保持「源码运行」的唯一入口，行为完全不变（服务器/浏览器模式）；
  * 本入口只服务 Electron 桌面壳：import app 后以 desktop 模式启动 Waitress，
    监听 127.0.0.1:5001（Electron 轮询该端口等待就绪）。

关键约定（与 electron/src/main.ts、desktop.spec 三方对齐）：
  * REGISTRY_DATA_DIR   —— 可写数据根（备份/上传/检索索引/同步包/崩溃日志），
                           Electron 设为 userData；未设时回退可执行文件目录。
  * REGISTRY_RUN_MODE   —— 固定为 desktop（app.py 据此只绑回环、不对外）。
  * REGISTRY_DB_PATH / SQLITE_PATH —— 数据库落点，Electron 设为 userData/data/app.db。

为什么监听 127.0.0.1 而不是 0.0.0.0：
  桌面单机场景把 Flask 暴露到局域网纯属攻击面（此前 server 模式绑 0.0.0.0 是
  服务器部署假设）。desktop 模式在 app.py 内分流，这里只负责把模式告诉它。
"""

import os
import sys

# 必须在 import app 之前设置：app.py 在 import 期读取 RUN_MODE 并解析数据根
os.environ.setdefault('REGISTRY_RUN_MODE', 'desktop')

# PyInstaller 解包目录（_MEIPASS）里有 backend/、static/（前端构建产物），
# app.py 以自身定位为准；frozen 态它用 sys._MEIPASS，无需额外 sys.path 处理。

import app as flask_app  # noqa: E402  (打包态单例入口)


def main() -> None:
    flask_app.init_db()
    import waitress
    # 与 app.py __main__ 的 desktop 分支一致：回环 + 8 线程足够单机 GUI
    waitress.serve(
        flask_app.app,
        host='127.0.0.1',
        port=5001,
        threads=8,
        channel_timeout=120,
    )


if __name__ == '__main__':
    main()
