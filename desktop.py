# -*- coding: utf-8 -*-
import threading
import webview
from app import app
import time

def start_flask():
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)

if __name__ == '__main__':
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(2)
    webview.create_window('动态数据登记系统', 'http://127.0.0.1:5001', width=1200, height=800)
    webview.start()