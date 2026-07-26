# -*- coding: utf-8 -*-
"""
动态数据登记系统 - Locust 压力测试脚本
目标：验证 150-170 人并发下的系统性能

认证机制（双保险）：
  1. Flask cookie-based session（HttpUser 自动管理 cookie）
  2. 每个请求显式携带 Authorization: Bearer {token} 头
     （与前端 Axios 拦截器行为完全一致）

使用方法：
  1. pip install locust
  2. python app.py (启动后端，Waitress 模式)
  3. Web UI 模式：locust -f locustfile.py --host=http://127.0.0.1:5001
     浏览器打开 http://localhost:8089
  4. 无界面模式：locust -f locustfile.py --host=http://127.0.0.1:5001 --headless -u 170 -r 10 --run-time 5m
"""

from locust import HttpUser, task, between, events
import json
import random
import string

# ──────────────────────── 工具函数 ────────────────────────


def random_text(length=8):
    """生成随机字符串（模拟测试数据）"""
    chars = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    return f'压测_{chars}'


def random_field_value(field_type, col_name):
    """根据字段类型生成随机值"""
    if field_type == 'number':
        return random.randint(1, 99999)
    elif field_type == 'boolean':
        return random.choice([1, 0])
    elif field_type == 'date':
        return f'2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}'
    elif field_type == 'select':
        return f'选项{random.randint(1,5)}'
    else:
        return random_text()


def check_response(response, name=''):
    """统一检查响应，自动标记成功/失败"""
    if response.status_code >= 500:
        response.failure(f'[{name}] 服务器 500 错误: {response.text[:200]}')
    elif response.status_code >= 400:
        response.failure(f'[{name}] 客户端错误 {response.status_code}: {response.text[:200]}')
    else:
        try:
            data = response.json()
            if 'error' in data:
                response.failure(f'[{name}] 业务错误: {data["error"]}')
        except (json.JSONDecodeError, ValueError):
            response.failure(f'[{name}] 非 JSON 响应: {response.text[:200]}')


# ──────────────────────── 事件钩子 ────────────────────────


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """压测开始前打印提示"""
    print('=' * 60)
    print(f'[Locust] 开始压力测试')
    print(f'[Locust] 目标: {environment.host}')
    print(f'[Locust] 预期并发: 150-170 用户')
    print('=' * 60)


# ──────────────────────── 用户行为类 ────────────────────────

class RegistryUser(HttpUser):
    """
    模拟真实用户操作的主测试类。

    认证机制（双保险）：
    - Flask cookie-based session（HttpUser 自动管理）
    - 每个请求显式携带 Authorization: Bearer {token} 头
      （在 _auth_headers() 中统一构建，所有请求调用）

    任务权重设计：
    - 读操作占 ~80%（查看字段、查看数据、查看统计、查看日志）
    - 写操作占 ~20%（新增、编辑、删除）
    """

    wait_time = between(1, 3)  # 模拟真实用户操作间隔 1-3 秒

    # 账户池
    ACCOUNTS = [
        {'username': 'boss', 'password': '123456'},
        {'username': 'hr', 'password': '123456'},
        {'username': 'employee', 'password': '123456'},
    ]

    def on_start(self):
        """
        每个虚拟用户启动时执行一次：登录获取 token。
        同时通过 self.client.headers 设置全局 Authorization 头，
        确保所有请求自动携带认证信息。
        """
        account = random.choice(self.ACCOUNTS)
        resp = self.client.post(
            '/api/login',
            json={'username': account['username'], 'password': account['password']},
            name='POST /api/login'
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get('token', '')
            self.username = account['username']
            # 设置全局 Authorization 头（HttpSession 会自动为所有请求携带）
            self.client.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
            print(f'[Locust] 用户 {self.username} 登录成功, token={self.token}')
        else:
            self.token = ''
            self.username = None
            print(f'[Locust] 用户 {account["username"]} 登录失败: {resp.status_code}')

        # 缓存字段列表
        self._columns_cache = None

    def _auth_headers(self):
        """
        返回认证请求头（双保险：即使全局 headers 失效也能保证认证）。
        如果 self.client.headers 已包含 Authorization，此方法作为兜底。
        """
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    def _get_columns(self):
        """获取并缓存字段定义（避免重复请求）"""
        if self._columns_cache is None:
            resp = self.client.get(
                '/api/columns',
                name='GET /api/columns',
                headers=self._auth_headers()
            )
            if resp.status_code == 200:
                self._columns_cache = resp.json()
            else:
                self._columns_cache = []
        return self._columns_cache

    # ──────── 高频操作（读）────────

    @task(10)
    def view_columns(self):
        """高频：查看字段列表"""
        with self.client.get(
            '/api/columns',
            name='GET /api/columns',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '查看字段')
            if resp.status_code == 200:
                self._columns_cache = resp.json()

    @task(10)
    def view_rows(self):
        """高频：查看数据列表（分页）"""
        page = random.randint(1, 3)
        page_size = random.choice([10, 20, 50])
        with self.client.get(
            f'/api/rows?page={page}&pageSize={page_size}',
            name='GET /api/rows',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '查看数据')

    @task(3)
    def view_stats_fields(self):
        """高频：获取可统计的字段列表"""
        with self.client.get(
            '/api/stats/fields',
            name='GET /api/stats/fields',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '统计字段')

    @task(2)
    def view_me(self):
        """中频：获取当前用户信息"""
        with self.client.get(
            '/api/me',
            name='GET /api/me',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '用户信息')

    # ──────── 中频操作（写）────────

    @task(3)
    def add_row(self):
        """中频：新增数据"""
        columns = self._get_columns()
        if not columns:
            return

        data = {}
        for col in columns[:min(len(columns), 5)]:
            data[col['name']] = random_field_value(col.get('field_type', 'text'), col['name'])

        with self.client.post(
            '/api/rows',
            json=data,
            name='POST /api/rows',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '新增数据')

    @task(2)
    def edit_row(self):
        """中频：编辑数据"""
        columns = self._get_columns()
        if not columns:
            return

        resp = self.client.get(
            '/api/rows?page=1&pageSize=20',
            name='GET /api/rows',
            headers=self._auth_headers()
        )
        if resp.status_code != 200:
            return

        rows = resp.json().get('data', [])
        if not rows:
            return

        row = random.choice(rows)
        col = random.choice(columns)
        data = {col['name']: random_field_value(col.get('field_type', 'text'), col['name'])}

        with self.client.put(
            f'/api/rows/{row["id"]}',
            json=data,
            name='PUT /api/rows/{id}',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '编辑数据')

    # ──────── 低频操作 ────────

    @task(1)
    def delete_row(self):
        """低频：删除数据（仅 boss 有删除权限）"""
        if self.username != 'boss':
            return

        resp = self.client.get(
            '/api/rows?page=1&pageSize=20',
            name='GET /api/rows',
            headers=self._auth_headers()
        )
        if resp.status_code != 200:
            return

        rows = resp.json().get('data', [])
        if len(rows) <= 5:
            return

        row = random.choice(rows)
        with self.client.delete(
            f'/api/rows/{row["id"]}',
            name='DELETE /api/rows/{id}',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '删除数据')

    @task(1)
    def view_stats(self):
        """低频：查看统计数据"""
        columns = self._get_columns()
        if not columns:
            return

        col = random.choice(columns)
        with self.client.get(
            f'/api/stats?field={col["name"]}',
            name='GET /api/stats',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '查看统计')

    @task(1)
    def view_logs(self):
        """低频：查看操作日志"""
        page = random.randint(1, 3)
        with self.client.get(
            f'/api/logs?page={page}&pageSize=20',
            name='GET /api/logs',
            headers={'Authorization': f'Bearer {self.token}'} if self.token else {},
            catch_response=True
        ) as resp:
            check_response(resp, '查看日志')

    @task(1)
    def view_audit_count(self):
        """低频：查看待审核数量"""
        with self.client.get(
            '/api/audit/count',
            name='GET /api/audit/count',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '审核计数')

    @task(1)
    def health_check(self):
        """低频：健康检查"""
        with self.client.get(
            '/api/health',
            name='GET /api/health',
            headers=self._auth_headers(),
            catch_response=True
        ) as resp:
            check_response(resp, '健康检查')