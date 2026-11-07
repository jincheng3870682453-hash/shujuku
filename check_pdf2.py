# -*- coding: utf-8 -*-
"""深挖 PDF 里的资源类型 + 提取文本确认内容"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pypdf import PdfReader

path = r'C:\Users\69215\Desktop\dynamic_registry\demo\ddrs_whitepaper.pdf'
r = PdfReader(path)

print('=== 元数据 ===')
m = r.metadata
for k, v in (m or {}).items():
    print(' ', k, '=', v)

print('\n=== 每页资源(XObject/图像/字体等) ===')
for i, page in enumerate(r.pages):
    res = page.get('/Resources')
    kinds = []
    if res:
        if '/XObject' in res:
            xo = res['/XObject'].get_object()
            subs = {}
            for nm, ob in xo.items():
                o = ob.get_object()
                s = str(o.get('/Subtype', '?'))
                subs[s] = subs.get(s, 0) + 1
            kinds.append('XObject: ' + str(subs))
        if '/Font' in res:
            kinds.append('Font: yes')
        if '/ColorSpace' in res:
            kinds.append('ColorSpace: yes')
    else:
        kinds.append('无资源')
    print('  P%d: %s' % (i+1, ' | '.join(kinds)))

print('\n=== 文本预览(前1200字) ===')
all_text = ''
for i, page in enumerate(r.pages):
    t = page.extract_text() or ''
    all_text += t
    print('--- P%d (%d字符) ---' % (i+1, len(t)))
print('\n总字符数:', len(all_text))
print('--- 开头 ---')
print(all_text[:1200])
print('--- 结尾 ---')
print(all_text[-800:])
