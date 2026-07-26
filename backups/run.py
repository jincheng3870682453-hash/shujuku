# -*- coding: utf-8 -*-
from app import app
import threading
import webbrowser

if __name__ == '__main__':
    port = 5001
    url = f'http://127.0.0.1:{port}'
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f'🚀 动态数据登记系统已启动: {url}')
    print('   按 Ctrl+C 可停止服务')
    app.run(host='127.0.0.1', port=port, debug=False)