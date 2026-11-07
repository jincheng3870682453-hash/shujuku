# -*- coding: utf-8 -*-
import re, json, sys

sys.stdout.reconfigure(encoding='utf-8')

html = open(r'C:\Users\69215\AppData\Local\Temp\xhs-note2.html', encoding='utf-8', errors='ignore').read()

# 提取标题
m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
print('TITLE:', m.group(1).strip() if m else 'N/A')

# 提取 __INITIAL_STATE__
m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.S)
if not m:
    m = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\})</script>', html, re.S)
state = None
if m:
    raw = m.group(1)
    try:
        state = json.loads(raw)
        print('INITIAL_STATE parsed OK')
    except Exception as e:
        print('JSON parse fail:', e)
        # 截断打印前2000字符看看
        print(raw[:2000])
else:
    print('NO INITIAL_STATE')

# 尝试从 state 提取笔记
if state:
    def find_key(obj, key, path=''):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == key:
                    found.append(v)
                found += find_key(v, key, path + '.' + k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found += find_key(v, key, path + f'[{i}]')
        return found

    # 找 note 数据
    note_list = find_key(state, 'noteDetailMap') or find_key(state, 'noteMap') or []
    if note_list:
        for note in note_list:
            if isinstance(note, dict):
                data = note.get('note', note)
                title = data.get('title', '')
                desc = data.get('desc', '')
                print('--- NOTE ---')
                print('标题:', title)
                print('正文:', desc)
                print('点赞:', data.get('likedCount', 'N/A'))
                print('收藏:', data.get('collectedCount', 'N/A'))
                print('评论数:', data.get('commentCount', 'N/A'))
                break

    # 找评论
    comments = find_key(state, 'comments') or []
    print('\n=== 评论数:', len(comments) if comments else 'N/A')
    if comments and isinstance(comments, list):
        for c in comments[:60]:
            if isinstance(c, dict):
                text = c.get('content') or c.get('text') or c.get('desc') or ''
                like = c.get('likeCount') or c.get('likedCount') or 0
                nick = c.get('userInfo', {}).get('nickname', '') if isinstance(c.get('userInfo'), dict) else ''
                if text:
                    print(f'[{like}赞] {nick}: {text}')
