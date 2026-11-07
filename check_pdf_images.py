# -*- coding: utf-8 -*-
"""检查 PDF 内嵌图片是否完整、能否正常解码"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

path = r'C:\Users\69215\Desktop\dynamic_registry\demo\ddrs_whitepaper.pdf'
r = PdfReader(path)
print('PDF 页数:', len(r.pages))
img_count = 0
bad = []
for i, page in enumerate(r.pages):
    res = page.get('/Resources')
    if not res or '/XObject' not in res:
        continue
    xo = res['/XObject'].get_object()
    for name, obj in xo.items():
        o = obj.get_object()
        if o.get('/Subtype') == '/Image':
            img_count += 1
            w = o.get('/Width'); h = o.get('/Height'); f = str(o.get('/Filter'))
            try:
                data = o.get_data()
                ok = True
                msg = ''
                # 校验常见格式的文件头
                if data[:2] == b'\xff\xd8':
                    if data[2:3] != b'\xff':
                        msg = 'JPEG 头异常'
                elif data[:8] == b'\x89PNG\r\n\x1a\n':
                    msg = ''
            except Exception as e:
                ok = False
                msg = '解码失败: %s' % e
                data = b''
            status = 'OK' if ok else '损坏'
            print('  P%d %s %dx%d filter=%s data=%dB %s %s' % (i+1, name, w, h, f, len(data), status, msg))
            if not ok:
                bad.append((i+1, name))
print('图片总数:', img_count)
print('损坏图片:', bad if bad else '无')
