import { useState } from 'react';
import { Form, Input, Button, App } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

export default function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { message } = App.useApp();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await authApi.login(values);
      localStorage.setItem('token', res.token);
      localStorage.setItem('user', JSON.stringify({ username: res.user.username, role: res.user.role }));
      message.success('欢迎回来');
      navigate('/stats', { replace: true });
    } catch (err: any) {
      const msg = err?.response?.data?.error || '用户名或密码错误';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: 'var(--space-6)',
      background: 'var(--surface-canvas)',
      fontFamily: 'var(--font-sans)',
    }}>
      <div style={{
        width: 380,
        maxWidth: '100%',
        padding: 'var(--space-8)',
        background: 'var(--surface-base)',
        border: '1px solid var(--line-frame)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
      }}>
        {/* 品牌标识 + 标题 */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
          <div style={{
            width: 44,
            height: 44,
            borderRadius: 'var(--radius-lg)',
            background: 'var(--ink-primary)',
            color: 'var(--ink-inverse)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 'var(--space-4)',
          }}>
            <LockOutlined style={{ fontSize: 20 }} />
          </div>
          <h1 className="page-title">动态数据登记系统</h1>
          <p className="page-subtitle" style={{ margin: 'var(--space-1) 0 0' }}>请输入账号密码登录</p>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          layout="vertical"
          size="large"
          autoComplete="off"
          initialValues={{ remember: true }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
            style={{ marginBottom: 'var(--space-4)' }}
          >
            {/* size="large" → controlHeight 40；圆角取 L3 --radius-md */}
            <Input
              placeholder="用户名"
              autoFocus
              style={{ height: 40, borderRadius: 'var(--radius-md)', fontSize: 'var(--fs-15)' }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
            style={{ marginBottom: 'var(--space-6)' }}
          >
            <Input.Password
              placeholder="密码"
              style={{ height: 40, borderRadius: 'var(--radius-md)', fontSize: 'var(--fs-15)' }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              style={{
                height: 40,
                borderRadius: 'var(--radius-md)',
                fontSize: 'var(--fs-15)',
                fontWeight: 500,
              }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>

        <p className="page-subtitle" style={{ margin: 'var(--space-6) 0 0', textAlign: 'center' }}>
          忘记密码请联系管理员
        </p>
      </div>
    </div>
  );
}
