import { useState } from 'react';
import { Form, Input, Button, Typography, App } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';

const { Title, Text } = Typography;

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
      background: 'var(--tx-body-bg, #08090a)',
      fontFamily: "var(--font-sans)",
    }}>
      {/* 背景装饰 - 使用纹理系统光晕 */}
      <div style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        background: 'var(--tx-body-gradient)',
        zIndex: 0,
      }} />

      <div className="login-card" style={{
        width: 380,
        padding: '40px 36px',
        background: 'var(--tx-card-bg, #0f1011)',
        backdropFilter: 'var(--tx-card-backdrop, none)',
        WebkitBackdropFilter: 'var(--tx-card-backdrop, none)',
        borderRadius: 14,
        border: 'var(--tx-card-border, 0.5px solid #23252a)',
        boxShadow: 'var(--tx-card-shadow, 0 8px 32px rgba(0,0,0,0.5))',
        position: 'relative',
        zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: 'var(--brand-accent-dim, rgba(94,106,210,0.12))',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
          }}>
            <LockOutlined style={{ fontSize: 20, color: 'var(--brand-accent, #5e6ad2)' }} />
          </div>
          <Title level={3} style={{ margin: 0, color: 'var(--surface-bone, #e5e5e6)', fontWeight: 500, letterSpacing: '-0.01em' }}>
            动态数据登记系统
          </Title>
          <Text style={{ color: 'var(--surface-ash, #62666d)', fontSize: 14, display: 'block', marginTop: 4 }}>
            请输入账号密码登录
          </Text>
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
            style={{ marginBottom: 16 }}
          >
            <Input
              placeholder="用户名"
              autoFocus
              style={{
                height: 44,
                borderRadius: 8,
                background: 'var(--tx-input-bg, var(--surface-obsidian, #161718))',
                borderColor: 'var(--surface-smoke, #383b3f)',
                color: 'var(--surface-mist, #d0d6e0)',
                fontSize: 15,
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
            style={{ marginBottom: 24 }}
          >
            <Input.Password
              placeholder="密码"
              style={{
                height: 44,
                borderRadius: 8,
                background: 'var(--tx-input-bg, var(--surface-obsidian, #161718))',
                borderColor: 'var(--surface-smoke, #383b3f)',
                color: 'var(--surface-mist, #d0d6e0)',
                fontSize: 15,
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: 44,
                borderRadius: 8,
                fontSize: 15,
                fontWeight: 500,
                background: 'var(--brand-accent, #5e6ad2)',
                border: 'none',
                boxShadow: 'var(--tx-btn-glow, 0 0 0 1px rgba(94,106,210,0.3), 0 2px 8px rgba(94,106,210,0.2))',
              }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', marginTop: 24 }}>
          <Text style={{ color: 'var(--surface-smoke, #383b3f)', fontSize: 12 }}>
            忘记密码请联系管理员
          </Text>
        </div>
      </div>
    </div>
  );
}
