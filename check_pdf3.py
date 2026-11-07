# -*- coding: utf-8 -*-
"""检查 PDF 的 Form XObject 内部是否包含图片"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pypdf import PdfReader

path = r'C:\Users\69215\Desktop\dynamic_registry\demo\ddrs_whitepaper.pdf'
r = PdfReader(path)
found = []

def walk(obj, depth=0):
    if depth > 8:
        return
    if hasattr(obj, 'get_object'):
        obj = obj.get_object()
    if isinstance(obj, dict):
        if obj.get('/Subtype') == '/Image':
            w = obj.get('/Width'); h = obj.get('/Height'); f = str(obj.get('/Filter'))
            try:
                data = obj.get_data()
                found.append((w, h, f, len(data)))
            except Exception as e:
                found.append((w, h, f, 'ERR:%s' % e))
        for k, v in obj.items():
            walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, depth + 1)

for i, page in enumerate(r.pages):
    walk(page.get('/Resources'), 0)

print('Form 内找到的图片对象数:', len(found))
for f in found:
    print('  ', f)
print('结论:', 'PDF 有图片' if found else 'PDF 完全无图片（纯矢量+文字）')
