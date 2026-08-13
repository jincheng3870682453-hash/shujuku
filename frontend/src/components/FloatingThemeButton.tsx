import { useState, useRef } from 'react';
import { Button, Drawer, Form, ColorPicker, Space, Typography, Divider, App } from 'antd';
import { BgColorsOutlined, ReloadOutlined } from '@ant-design/icons';
import { authApi } from '../api/auth';
import type { Color } from 'antd/es/color-picker';

const { Text } = Typography;

/** 将当前背景/主题同步保存到当前登录用户（按用户隔离存储） */
function syncUserThemeToServer() {
  try {
    let savedTheme: Record<string, string | number> = {};
    const raw = localStorage.getItem('theme');
    if (raw) savedTheme = JSON.parse(raw);
    authApi.saveUserTheme({
      theme: savedTheme,
      texture: localStorage.getItem('dashboard_texture') || 'glass',
      glass_alpha: Number(localStorage.getItem('glass_alpha') || 0.8),
      neon_accent: localStorage.getItem('neon_accent') || 'purple',
      bg_image: localStorage.getItem('bg_image'),
    }).catch(() => { /* 静默失败，不影响本地使用 */ });
  } catch { /* 忽略非关键错误 */ }
}

interface ThemeColors {
  primaryColor: string; backgroundColor: string; cardColor: string; textColor: string;
}

const DEFAULT_THEME: ThemeColors = {
  primaryColor: '#5e6ad2', backgroundColor: '#08090a', cardColor: '#0f1011', textColor: '#e5e5e6',
};

function loadTheme(): ThemeColors {
  try { const saved = localStorage.getItem('theme'); return saved ? { ...DEFAULT_THEME, ...JSON.parse(saved) } : DEFAULT_THEME; } catch { return DEFAULT_THEME; }
}

function applyTheme(t: ThemeColors) {
  const r = document.documentElement.style;
  r.setProperty('--accent-default', t.primaryColor);
  r.setProperty('--surface-root', t.backgroundColor);
  r.setProperty('--surface-card', t.cardColor);
  r.setProperty('--text-primary', t.textColor);
  localStorage.setItem('ui_colors', JSON.stringify(t));
}

export default function FloatingThemeButton() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeColors>(loadTheme);
  const { message } = App.useApp();
  // 颜色选择器拖动时频繁触发，防抖同步到后端
  const saveTimer = useRef<number | null>(null);
  const scheduleSave = () => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(syncUserThemeToServer, 500);
  };

  const handleChange = (key: keyof ThemeColors, hex: string) => {
    const updated = { ...theme, [key]: hex };
    setTheme(updated);
    applyTheme(updated);
    localStorage.setItem('theme', JSON.stringify(updated));
    scheduleSave();
  };

  const handleReset = () => {
    setTheme(DEFAULT_THEME);
    applyTheme(DEFAULT_THEME);
    localStorage.setItem('theme', JSON.stringify(DEFAULT_THEME));
    message.success('已恢复默认配色');
    syncUserThemeToServer();
  };

  return (
    <>
      {/* 浮动按钮 */}
      <div style={{
        position: 'fixed', bottom: 24, right: 24, zIndex: 999,
      }}>
        <Button
          shape="circle"
          size="large"
          icon={<BgColorsOutlined />}
          onClick={() => setOpen(true)}
          style={{
            width: 44, height: 44,
            background: 'var(--surface-card)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-secondary)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-default)'; e.currentTarget.style.color = 'var(--accent-default)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
        />
      </div>

      <Drawer
        title="主题配色"
        placement="right"
        onClose={() => setOpen(false)}
        open={open}
        width={360}
      >
        <Form layout="vertical">
          {[
            { label: '品牌强调色', key: 'primaryColor' as keyof ThemeColors },
            { label: '背景色', key: 'backgroundColor' as keyof ThemeColors },
            { label: '卡片背景色', key: 'cardColor' as keyof ThemeColors },
            { label: '文字颜色', key: 'textColor' as keyof ThemeColors },
          ].map(({ label, key }) => (
            <Form.Item key={key} label={<span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>}>
              <Space>
                <ColorPicker
                  value={theme[key]}
                  onChange={(c: Color) => handleChange(key, c.toHexString())}
                />
                <Text code style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{theme[key]}</Text>
              </Space>
            </Form.Item>
          ))}
        </Form>
        <Divider />
        <Button block icon={<ReloadOutlined />} onClick={handleReset}>恢复默认配色</Button>

        <Divider />
        <div style={{
          padding: 16,
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-default)',
          background: theme.backgroundColor,
        }}>
          <div style={{
            padding: 12,
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-default)',
            background: theme.cardColor,
          }}>
            <span style={{ color: theme.primaryColor, fontWeight: 500, fontSize: 13 }}>预览卡片</span>
            <br />
            <span style={{ color: theme.textColor, fontSize: 12 }}>文本预览示例</span>
          </div>
        </div>
      </Drawer>
    </>
  );
}
