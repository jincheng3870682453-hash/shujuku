# -*- coding: utf-8 -*-
"""测试数据统计看板 API"""
import urllib.request
import json
import http.cookiejar

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. 登录
req = urllib.request.Request(
    'http://127.0.0.1:5001/api/login',
    data=json.dumps({'username': 'boss', 'password': '123456'}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = op.open(req)
login_data = json.loads(resp.read())
print('1. 登录成功:', login_data['username'], '| view_stats 权限:', 'view_stats' in login_data['permissions'])

# 2. 查看现有列
req = urllib.request.Request('http://127.0.0.1:5001/api/columns')
resp = op.open(req)
cols = json.loads(resp.read())
print(f'2. 当前列数量: {len(cols)}')
for c in cols:
    print(f'   - {c["name"]} ({c["label"]}) [{c["field_type"]}]')

# 3. 如果列不够，添加测试数据
if len(cols) < 3:
    print('3. 添加测试字段...')
    fields = [
        {'label': '部门', 'field_type': 'select', 'options': '技术部,市场部,人事部,财务部'},
        {'label': '工资', 'field_type': 'number'},
        {'label': '入职日期', 'field_type': 'date'},
    ]
    col_map = {}
    for f in fields:
        req = urllib.request.Request(
            'http://127.0.0.1:5001/api/columns',
            data=json.dumps(f).encode(),
            headers={'Content-Type': 'application/json'}
        )
        resp = op.open(req)
        result = json.loads(resp.read())
        if 'name' in result:
            col_map[f['label']] = result['name']
            print(f'   ✓ 添加字段: {f["label"]} -> {result["name"]}')
        else:
            print(f'   ✗ {f["label"]}: {result}')
else:
    col_map = {c['label']: c['name'] for c in cols}

# 4. 如果有列，添加一些测试数据
if col_map:
    print('4. 检查数据行...')
    req = urllib.request.Request('http://127.0.0.1:5001/api/rows')
    resp = op.open(req)
    rows = json.loads(resp.read())
    print(f'   当前行数: {len(rows)}')

    if len(rows) < 5:
        print('   添加测试数据...')
        test_data_list = [
            {col_map.get('部门', next(iter(col_map.values()))): '技术部',
             col_map.get('工资', next(iter(col_map.values()))): '12000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-01-15'},
            {col_map.get('部门', next(iter(col_map.values()))): '技术部',
             col_map.get('工资', next(iter(col_map.values()))): '15000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-03-20'},
            {col_map.get('部门', next(iter(col_map.values()))): '市场部',
             col_map.get('工资', next(iter(col_map.values()))): '9000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-02-10'},
            {col_map.get('部门', next(iter(col_map.values()))): '市场部',
             col_map.get('工资', next(iter(col_map.values()))): '11000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-05-08'},
            {col_map.get('部门', next(iter(col_map.values()))): '人事部',
             col_map.get('工资', next(iter(col_map.values()))): '10000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-04-01'},
            {col_map.get('部门', next(iter(col_map.values()))): '财务部',
             col_map.get('工资', next(iter(col_map.values()))): '13000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-06-18'},
            {col_map.get('部门', next(iter(col_map.values()))): '技术部',
             col_map.get('工资', next(iter(col_map.values()))): '18000',
             col_map.get('入职日期', next(iter(col_map.values()))): '2024-07-22'},
        ]
        for td in test_data_list:
            req = urllib.request.Request(
                'http://127.0.0.1:5001/api/rows',
                data=json.dumps(td).encode(),
                headers={'Content-Type': 'application/json'}
            )
            try:
                resp = op.open(req)
                result = json.loads(resp.read())
                if 'pending' in result:
                    pass  # 审核模式
                else:
                    print(f'   ✓ 添加数据行')
            except Exception as e:
                print(f'   ✗ 添加失败: {e}')

    # 5. 测试统计接口
    print('\n5. 测试统计接口...')

    # 获取最新列信息
    req = urllib.request.Request('http://127.0.0.1:5001/api/columns')
    resp = op.open(req)
    cols = json.loads(resp.read())
    col_map = {c['label']: c['name'] for c in cols}

    for label, name in col_map.items():
        print(f'\n--- 统计字段: {label} ({name}) ---')
        req = urllib.request.Request(
            'http://127.0.0.1:5001/api/stats',
            data=json.dumps({'field_name': name, 'chart_type': 'auto'}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        try:
            resp = op.open(req)
            result = json.loads(resp.read())
            print(f'   类型: {result.get("field_type")}')
            print(f'   总计: {result.get("total")}')
            print(f'   Labels: {result.get("labels")}')
            print(f'   Values: {result.get("values")}')
            if 'sum' in result:
                print(f'   合计: {result["sum"]}, 平均: {result["avg"]}, 最大: {result["max"]}, 最小: {result["min"]}')
        except urllib.error.HTTPError as e:
            print(f'   HTTP Error: {e.code} - {e.read().decode()}')

    # 6. 测试空数据统计
    print('\n\n6. 测试空字段统计...')
    req = urllib.request.Request(
        'http://127.0.0.1:5001/api/stats',
        data=json.dumps({'field_name': 'non_existent_field', 'chart_type': 'pie'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        resp = op.open(req)
        print(f'   非预期结果: {resp.read().decode()}')
    except urllib.error.HTTPError as e:
        result = json.loads(e.read().decode())
        print(f'   预期错误: {e.code} - {result.get("error")}')

    print('\n\n✅ 所有测试完成!')
    print('   现在可以在浏览器中访问 http://127.0.0.1:5001 查看完整效果')
    print('   boss 登录后，导航栏应显示「📊 数据统计」按钮')
else:
    print('\n❌ 没有列定义，无法继续测试')