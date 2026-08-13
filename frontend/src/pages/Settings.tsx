import { useState, useEffect, useRef } from 'react';
import {
  Card, Form, Select, Input, InputNumber, Button, Typography, message, Spin, Alert, Tag, Descriptions, Divider, Tabs, ColorPicker, Space, Image, Slider,
} from 'antd';
import { SaveOutlined, ReloadOutlined, LinkOutlined, BgColorsOutlined, UploadOutlined, PictureOutlined, DeleteOutlined, SwapOutlined, ThunderboltOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '../api/settings';
import { authApi } from '../api/auth';
import type { AppSettings, DBEngine } from '../types/data';
import type { Color } from 'antd/es/color-picker';

const { Title, Text, Paragraph } = Typography;

const BG_IMAGE_KEY = 'bg_image';
const MAX_FILE_SIZE = 5 * 1024 * 1024;

/** 将当前 localStorage 中的背景/主题同步保存到当前登录用户（按用户隔离存储） */
function syncUserThemeToServer() {
  try {
    const t = loadTheme();
    authApi.saveUserTheme({
      theme: t,
      texture: localStorage.getItem('dashboard_texture') || 'glass',
      glass_alpha: Number(localStorage.getItem('glass_alpha') || String(t.cardOpacity / 100)),
      neon_accent: localStorage.getItem('neon_accent') || 'purple',
      bg_image: loadBgImage(),
    }).catch(() => { /* 静默失败，不影响本地使用 */ });
  } catch { /* 忽略非关键错误 */ }
}

interface ThemeColors {
  primaryColor: string; backgroundColor: string; cardColor: string; textColor: string; cardOpacity: number;
}

const DEFAULT_THEME: ThemeColors = {
  primaryColor: '#5e6ad2', backgroundColor: '#08090a', cardColor: '#0f1011', textColor: '#e5e5e6', cardOpacity: 80,
};

function loadTheme(): ThemeColors {
  try { const saved = localStorage.getItem('theme'); return saved ? { ...DEFAULT_THEME, ...JSON.parse(saved) } : DEFAULT_THEME; } catch { return DEFAULT_THEME; }
}
function applyTheme(theme: ThemeColors) {
  const root = document.documentElement;
  root.style.setProperty('--accent-default', theme.primaryColor);
  root.style.setProperty('--surface-root', theme.backgroundColor);
  root.style.setProperty('--surface-card', theme.cardColor);
  root.style.setProperty('--text-primary', theme.textColor);
  // 同步保存到 ui_colors（与其他组件共享）
  localStorage.setItem('ui_colors', JSON.stringify(theme));
}

/** 全局背景图管理 */
function loadBgImage(): string | null {
  return localStorage.getItem(BG_IMAGE_KEY);
}
function saveBgImage(base64: string | null) {
  if (base64) {
    localStorage.setItem(BG_IMAGE_KEY, base64);
  } else {
    localStorage.removeItem(BG_IMAGE_KEY);
  }
}
/* ================================================================
   2.1  默认渐变背景（双层光晕：紫色 + 蓝色，底层 #0A0A0F）
   ================================================================ */
const DEFAULT_BG_GRADIENT = [
  'radial-gradient(ellipse 80% 50% at 20% 0%, rgba(124,58,237,0.12), transparent)',
  'radial-gradient(ellipse 60% 40% at 80% 100%, rgba(59,130,246,0.08), transparent)',
  '#0A0A0F',
].join(',');

function applyDefaultGradientBg() {
  document.body.style.background = DEFAULT_BG_GRADIENT;
}

/* ---- 自定义背景图 ---- */
function applyBgImage(base64: string | null) {
  if (base64) {
    document.body.style.background = `url(${base64}) center / cover no-repeat fixed`;
  } else {
    applyDefaultGradientBg();
  }
}

/* ================================================================
   2.2  玻璃透明度 — 通过 CSS 变量 --tx-glass-alpha 控制
   不再使用 JS 注入 <style> 标签，全部由 textures.css 驱动
   ================================================================ */

/** 设置玻璃卡片透明度 CSS 变量 */
function applyGlassOpacity(opacity: number) {
  document.documentElement.style.setProperty('--tx-glass-alpha', String(opacity / 100));
  localStorage.setItem('glass_alpha', String(opacity / 100));
}

// ==== 启动时立即执行：玻璃/透明质感下应用背景图 ====
const savedTexture = localStorage.getItem('dashboard_texture') || 'glass';
if (savedTexture === 'glass' || savedTexture === 'transparent') {
  applyBgImage(loadBgImage());
}
if (savedTexture === 'glass') {
  // 恢复保存的玻璃透明度
  const savedAlpha = localStorage.getItem('glass_alpha');
  if (savedAlpha !== null) {
    document.documentElement.style.setProperty('--tx-glass-alpha', savedAlpha);
  }
}

// 恢复霓虹品牌色
const savedNeonAccent = localStorage.getItem('neon_accent') || 'purple';
if (savedNeonAccent === 'cyan') {
  document.documentElement.setAttribute('data-neon-accent', 'cyan');
}

/* ================================================================
   背景质感系统 — 8 种 Dashboard 质感
   ================================================================ */

interface TextureOption {
  key: string;
  name: string;
  description: string;
  /** 预览缩略图的行内样式 */
  previewStyle: React.CSSProperties;
}

const TEXTURES: TextureOption[] = [
  {
    key: 'glass',
    name: '玻璃质感',
    description: '半透明毛玻璃 + 光晕渐变，通透现代',
    previewStyle: {
      background:
        'radial-gradient(ellipse 80% 50% at 20% 0%, rgba(124,58,237,0.2), transparent),' +
        'radial-gradient(ellipse 60% 40% at 80% 100%, rgba(59,130,246,0.15), transparent),' +
        '#0A0A0F',
    },
  },
  {
    key: 'frosted',
    name: '磨砂质感',
    description: '纯色哑光 + 噪点纹理，克制内敛',
    previewStyle: {
      background: '#1E1E24',
      backgroundImage:
        'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 64 64\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.7\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'0.08\'/%3E%3C/svg%3E")',
      backgroundSize: '64px 64px',
    },
  },
  {
    key: 'metallic',
    name: '金属质感',
    description: '拉丝渐变 + 金属光泽，冷峻硬朗',
    previewStyle: {
      background: 'linear-gradient(135deg, #2a2a2a, #1a1a1a)',
      backgroundImage:
        'repeating-linear-gradient(90deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 3px),' +
        'linear-gradient(135deg, #2a2a2a, #1a1a1a)',
    },
  },
  {
    key: 'paper',
    name: '纸本质感',
    description: '暖色纤维纹理 + 柔和阴影，亲和自然',
    previewStyle: {
      background: '#F7F6F3',
      backgroundImage:
        'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 64 64\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.85\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'0.04\'/%3E%3C/svg%3E")',
      backgroundSize: '64px 64px',
      border: '1px solid #E0DFD9',
    },
  },
  {
    key: 'neon',
    name: '霓虹质感',
    description: '扫描线 + 网格发光，赛博朋克',
    previewStyle: {
      background: '#050508',
      backgroundImage:
        'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.15) 2px, rgba(0,0,0,0.15) 4px),' +
        'linear-gradient(rgba(124,58,237,0.08) 1px, transparent 1px),' +
        'linear-gradient(90deg, rgba(124,58,237,0.08) 1px, transparent 1px)',
      backgroundSize: '100% 4px, 16px 16px, 16px 16px',
      border: '1px solid rgba(124,58,237,0.3)',
      boxShadow: '0 0 10px rgba(124,58,237,0.15)',
    },
  },
  {
    key: 'liquid-mesh',
    name: '液态网格',
    description: '四色流动渐变 + 高模糊度，柔和未来感',
    previewStyle: {
      background:
        'radial-gradient(ellipse at 30% 20%, rgba(124,58,237,0.35), transparent),' +
        'radial-gradient(ellipse at 70% 30%, rgba(59,130,246,0.3), transparent),' +
        'radial-gradient(ellipse at 50% 70%, rgba(6,182,212,0.25), transparent),' +
        'radial-gradient(ellipse at 80% 60%, rgba(236,72,153,0.2), transparent),' +
        '#0a0a14',
      backgroundSize: '200% 200%',
    },
  },
  {
    key: 'depth',
    name: '深度质感',
    description: '双层阴影雕刻 + 实体色，厚重立体',
    previewStyle: {
      background: '#1C1C24',
      border: 'none',
      boxShadow: '0 1px 0 rgba(255,255,255,0.03), 0 4px 12px rgba(0,0,0,0.5)',
    },
  },
  {
    key: 'flat',
    name: '极简平面',
    description: '纯色无修饰，零装饰纯功能',
    previewStyle: {
      background: '#141414',
      border: '1px solid #1F1F1F',
    },
  },
  {
    key: 'transparent',
    name: '透明质感',
    description: '完全透明，直接展示背景图',
    previewStyle: {
      background: 'transparent',
      border: '1px dashed rgba(255,255,255,0.15)',
    },
  },
];

/** 切换背景质感 */
function switchTexture(key: string) {
  // 清除 body 行内背景样式，让 CSS 变量完全接管
  document.body.style.background = '';

  // 处理玻璃/透明质感：重新应用背景图
  if (key === 'glass' || key === 'transparent') {
    const bg = loadBgImage();
    if (bg) {
      document.body.style.background = `url(${bg}) center / cover no-repeat fixed`;
    }
  }

  // 双属性同步：data-texture + data-theme
  document.documentElement.setAttribute('data-texture', key);
  document.documentElement.setAttribute('data-theme', key);

  // 持久化
  localStorage.setItem('dashboard_texture', key);

  // 150ms 淡入过渡
  document.documentElement.classList.add('texture-transitioning');
  setTimeout(() => document.documentElement.classList.remove('texture-transitioning'), 150);
}

/** 切换霓虹品牌色 */
function switchNeonAccent(accent: string) {
  if (accent === 'cyan') {
    document.documentElement.setAttribute('data-neon-accent', 'cyan');
  } else {
    document.documentElement.removeAttribute('data-neon-accent');
  }
  localStorage.setItem('neon_accent', accent);
}

function getCurrentTexture(): string {
  return localStorage.getItem('dashboard_texture') || 'glass';
}

function Settings() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<AppSettings>();
  const [testingMysql, setTestingMysql] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState<DBEngine>('sqlite');
  const [theme, setTheme] = useState<ThemeColors>(loadTheme);

  const [bgImage, setBgImage] = useState<string | null>(loadBgImage);
  const [bgPreviewUrl, setBgPreviewUrl] = useState<string | null>(bgImage);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 背景质感状态
  const [activeTexture, setActiveTexture] = useState<string>(getCurrentTexture);
  const [neonAccent, setNeonAccent] = useState<string>(() => localStorage.getItem('neon_accent') || 'purple');

  useEffect(() => { applyTheme(theme); }, [theme]);

  // 玻璃透明度：通过 CSS 变量 --tx-glass-alpha 驱动
  // 不再使用 JS 注入 <style> 标签，全部由 textures.css 接管
  useEffect(() => {
    applyGlassOpacity(theme.cardOpacity);
  }, [theme.cardOpacity]);

  useEffect(() => {
    // 玻璃/透明质感时应用背景图（其他质感由 CSS 变量接管）
    const currentTexture = document.documentElement.getAttribute('data-texture') || 'glass';
    if (currentTexture === 'glass' || currentTexture === 'transparent') {
      applyBgImage(bgImage);
    }
  }, [bgImage]);

  // 颜色/滑块频繁触发时防抖同步到后端
  const themeSaveTimer = useRef<number | null>(null);
  const scheduleThemeSave = () => {
    if (themeSaveTimer.current) window.clearTimeout(themeSaveTimer.current);
    themeSaveTimer.current = window.setTimeout(syncUserThemeToServer, 600);
  };

  const handleThemeChange = (key: keyof ThemeColors, value: string | number) => {
    const updated = { ...theme, [key]: value };
    setTheme(updated); applyTheme(updated); localStorage.setItem('theme', JSON.stringify(updated));
    scheduleThemeSave();
  };
  const resetTheme = () => {
    setTheme(DEFAULT_THEME); applyTheme(DEFAULT_THEME); localStorage.setItem('theme', JSON.stringify(DEFAULT_THEME));
    syncUserThemeToServer();
  };

  // 背景图处理
  const handleBgFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 检查文件类型
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      messageApi.error('仅支持 JPG、PNG、WebP 格式的图片');
      return;
    }

    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      messageApi.error('图片大小不能超过 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = (evt) => {
      const base64 = evt.target?.result as string;
      setBgPreviewUrl(base64);
      messageApi.success('图片加载成功，点击「保存背景」应用');
    };
    reader.onerror = () => {
      messageApi.error('图片读取失败，请重试');
    };
    reader.readAsDataURL(file);

    // 清理 input 以便重复选择同一文件
    e.target.value = '';
  };

  const handleSaveBgImage = () => {
    if (!bgPreviewUrl) {
      messageApi.warning('请先选择一张图片');
      return;
    }
    saveBgImage(bgPreviewUrl);
    const currentTexture = document.documentElement.getAttribute('data-texture') || 'glass';
    if (currentTexture === 'glass') {
      applyBgImage(bgPreviewUrl);
    }
    setBgImage(bgPreviewUrl);
    messageApi.success('背景图已保存并应用');
    syncUserThemeToServer();
  };

  const handleResetBgImage = () => {
    saveBgImage(null);
    const currentTexture = document.documentElement.getAttribute('data-texture') || 'glass';
    if (currentTexture === 'glass') {
      applyBgImage(null);
    }
    setBgImage(null);
    setBgPreviewUrl(null);
    messageApi.success('背景图已恢复为默认');
    syncUserThemeToServer();
  };

  const { data: settings, isLoading } = useQuery<AppSettings>({
    queryKey: ['settings'], queryFn: settingsApi.getSettings,
  });

  useEffect(() => {
    if (settings && !form.getFieldValue('db_engine')) { form.setFieldsValue(settings); setSelectedEngine(settings.db_engine); }
  }, [settings, form]);

  const updateMutation = useMutation({
    mutationFn: settingsApi.updateSettings,
    onSuccess: () => messageApi.success('设置已保存，切换数据库引擎需重启服务后生效'),
    onError: () => messageApi.error('保存失败'),
  });

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      await updateMutation.mutateAsync({
        db_engine: selectedEngine,
        mysql_host: values.mysql_host || '',
        mysql_port: values.mysql_port || 3306,
        mysql_user: values.mysql_user || '',
        mysql_password: values.mysql_password || '',
        mysql_database: values.mysql_database || '',
      } as any);
    } catch { /* noop */ }
  };

  const handleTestMysql = async () => {
    try {
      setTestingMysql(true);
      const values = await form.validateFields(['mysql_host', 'mysql_port', 'mysql_user', 'mysql_password', 'mysql_database']);
      console.log('[测试连接] 请求参数:', { host: values.mysql_host, port: values.mysql_port, user: values.mysql_user, password: values.mysql_password ? '***' : '(空)', database: values.mysql_database });
      const result = await settingsApi.testMysqlConnection({ host: values.mysql_host, port: values.mysql_port, user: values.mysql_user, password: values.mysql_password || '', database: values.mysql_database });
      if (result.success) messageApi.success('MySQL 连接测试成功');
      else messageApi.error(result.message || '连接测试失败');
    } catch { messageApi.error('请先填写完整的 MySQL 连接参数（主机、端口、用户名、数据库名）'); }
    finally { setTestingMysql(false); }
  };

  const themeTab = (
    <>
      {/* 自定义配色 */}
      <Card className="glass-card" style={{ marginBottom: 16 }}>
        <Title level={5}><BgColorsOutlined style={{ marginRight: 8 }} />自定义配色</Title>
        <Alert message="配色实时生效，自动保存到本地浏览器，重新打开页面时自动恢复" type="info" showIcon style={{ marginBottom: 16 }} />
        <Form layout="vertical" style={{ maxWidth: 560 }}>
          {[
            ['品牌强调色', 'primaryColor'],
            ['背景色', 'backgroundColor'],
            ['卡片背景色', 'cardColor'],
            ['文本颜色', 'textColor'],
          ].map(([label, key]) => (
            <Form.Item key={key} label={label}>
              <Space>
                <ColorPicker value={(theme as any)[key]} onChange={(c: Color) => handleThemeChange(key as keyof ThemeColors, c.toHexString())} />
                <Text code>{(theme as any)[key]}</Text>
              </Space>
            </Form.Item>
          ))}
          <Form.Item label="卡片不透明度">
            <Space style={{ width: '100%' }}>
              <Slider
                style={{ width: 200 }}
                min={10}
                max={100}
                step={5}
                value={theme.cardOpacity}
                onChange={(v) => handleThemeChange('cardOpacity', v)}
              />
              <Text code>{theme.cardOpacity}%</Text>
            </Space>
          </Form.Item>
          <Form.Item><Button onClick={resetTheme} icon={<ReloadOutlined />}>恢复默认配色</Button></Form.Item>
        </Form>

        <Divider />
        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', display: 'block', marginBottom: 12 }}>
          预览效果
        </span>

        {/* 暗色框架内的 mini 界面预览 */}
        <div
          style={{
            background: '#0a0b0d',
            borderRadius: 14,
            border: '1px solid var(--border-default)',
            padding: 14,
            maxWidth: 560,
            boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
          }}
        >
          {/* 窗口顶栏 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff5f57' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#febc2e' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#28c840' }} />
            <div
              style={{
                marginLeft: 'auto',
                height: 4,
                width: 80,
                borderRadius: 2,
                background: theme.primaryColor,
                opacity: 0.7,
              }}
            />
          </div>

          {/* mini 页面：有自定义背景图时用图，否则用双层光晕渐变 */}
          <div
            style={{
              background: bgPreviewUrl
                ? `url(${bgPreviewUrl}) center / cover no-repeat`
                : DEFAULT_BG_GRADIENT,
              borderRadius: 10,
              border: '1px solid var(--border-default)',
              padding: 12,
              minHeight: 110,
              position: 'relative',
            }}
          >
            {bgPreviewUrl && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  borderRadius: 10,
                  background: 'rgba(0,0,0,0.12)',
                  pointerEvents: 'none',
                }}
              />
            )}
            {/* mini 卡片：固定毛玻璃 rgba(20,20,30,α) + blur(16px) saturate(180%) */}
            <div
              style={{
                background: `rgba(20, 20, 30, ${theme.cardOpacity / 100})`,
                backdropFilter: 'blur(16px) saturate(180%)',
                WebkitBackdropFilter: 'blur(16px) saturate(180%)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: 8,
                padding: 12,
                position: 'relative',
                zIndex: 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: theme.primaryColor }}>示例卡片</span>
                <span
                  style={{
                    fontSize: 10,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: theme.primaryColor,
                    color: 'var(--text-inverse)',
                  }}
                >
                  标签
                </span>
              </div>
              <div style={{ color: theme.textColor, fontSize: 11, lineHeight: 1.5, marginBottom: 10 }}>
                这是文本颜色在实际界面中的显示效果。
              </div>
              <Button type="primary" size="small" style={{ fontSize: 11, height: 24 }}>
                示例按钮
              </Button>
            </div>
          </div>

          {/* 色块标注 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 10,
              marginTop: 12,
            }}
          >
            {[
              { label: '品牌强调色', value: theme.primaryColor },
              { label: '背景色', value: theme.backgroundColor },
              { label: '卡片背景色', value: theme.cardColor },
              { label: '文本颜色', value: theme.textColor },
            ].map(item => (
              <div key={item.label} style={{ textAlign: 'center' }}>
                <div
                  style={{
                    width: '100%',
                    height: 28,
                    borderRadius: 6,
                    background: item.value,
                    border: '1px solid var(--border-default)',
                    marginBottom: 4,
                  }}
                />
                <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* 自定义背景图 */}
      <Card className="glass-card">
        <Title level={5}><PictureOutlined style={{ marginRight: 8 }} />自定义背景图</Title>
        <Alert message="上传背景图会替换登录页和主界面的纯色渐变背景。图片以 base64 存储在本地浏览器中，最大支持 5MB。" type="info" showIcon style={{ marginBottom: 16 }} />

        {/* 当前状态 */}
        <div style={{ marginBottom: 16 }}>
          <Tag color={bgImage ? 'green' : 'default'}>
            {bgImage ? '已自定义' : '默认'}
          </Tag>
          <Text type="secondary" style={{ marginLeft: 8 }}>
            {bgImage ? '当前正在使用自定义背景图' : '当前使用默认双层光晕渐变背景'}
          </Text>
        </div>

        {/* 预览区 */}
        <div
          style={{
            width: '100%',
            maxWidth: 560,
            aspectRatio: '16 / 9',
            borderRadius: 8,
            overflow: 'hidden',
            border: '1px solid var(--border-default)',
            background: bgPreviewUrl
              ? `url(${bgPreviewUrl}) center / cover no-repeat`
              : DEFAULT_BG_GRADIENT,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
            position: 'relative',
          }}
        >
          {bgPreviewUrl ? (
            <Image
              src={bgPreviewUrl}
              preview={{ mask: '点击预览大图' }}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                position: 'absolute',
                top: 0,
                left: 0,
              }}
            />
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
              <PictureOutlined style={{ fontSize: 48, marginBottom: 8 }} />
              <div style={{ fontSize: 14 }}>暂无背景图</div>
              <div style={{ fontSize: 12 }}>上传图片后在此预览</div>
            </div>
          )}
        </div>

        {/* 上传与操作按钮 */}
        <Space wrap>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp"
            onChange={handleBgFileChange}
            style={{ display: 'none' }}
          />
          <Button
            icon={<UploadOutlined />}
            onClick={() => fileInputRef.current?.click()}
          >
            上传背景图
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveBgImage}
            disabled={!bgPreviewUrl || bgPreviewUrl === bgImage}
            className="gradient-bg"
            style={{ border: 'none' }}
          >
            保存背景
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleResetBgImage}
            disabled={!bgImage}
          >
            恢复默认
          </Button>
        </Space>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持 JPG、PNG、WebP 格式，最大 5MB
          </Text>
        </div>
      </Card>
    </>
  );

  const handleTextureChange = (key: string) => {
    setActiveTexture(key);
    switchTexture(key);
    syncUserThemeToServer();
  };

  const handleRandomTexture = () => {
    const others = TEXTURES.filter(t => t.key !== activeTexture);
    const pick = others[Math.floor(Math.random() * others.length)];
    handleTextureChange(pick.key);
  };

  const textureTab = (
    <Card className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}><EyeOutlined style={{ marginRight: 8 }} />背景质感</Title>
        <Button icon={<SwapOutlined />} onClick={handleRandomTexture} size="small">
          随机质感
        </Button>
      </div>

      <Alert
        message={`当前质感：${TEXTURES.find(t => t.key === activeTexture)?.name || '玻璃质感'}`}
        description="切换背景质感会改变整个 Dashboard 的视觉风格，包括卡片、侧栏、表格、弹窗等所有组件。效果实时应用，自动保存。"
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
      />

      {/* 质感选择网格 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 12,
        }}
      >
        {TEXTURES.map((t) => {
          const isActive = activeTexture === t.key;
          return (
            <div
              key={t.key}
              onClick={() => handleTextureChange(t.key)}
              style={{
                cursor: 'pointer',
                borderRadius: 10,
                border: isActive
                  ? `2px solid var(--brand-accent)`
                  : '2px solid rgba(255,255,255,0.08)',
                overflow: 'hidden',
                transition: 'border-color 200ms, box-shadow 200ms',
                boxShadow: isActive
                  ? '0 0 0 3px rgba(94,106,210,0.2)'
                  : 'none',
                background: 'transparent',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                  e.currentTarget.style.boxShadow = 'none';
                }
              }}
            >
              {/* 缩略图 */}
              <div
                style={{
                  ...t.previewStyle,
                  height: 72,
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {/* 缩略图中的 mini 卡片（模拟 UI 效果） */}
                <div
                  style={{
                    width: '70%',
                    height: 32,
                    borderRadius: 6,
                    background: t.key === 'paper'
                      ? 'rgba(0,0,0,0.05)'
                      : t.key === 'liquid-mesh'
                        ? 'rgba(255,255,255,0.1)'
                        : t.key === 'metallic'
                          ? 'linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02))'
                          : `rgba(${t.key === 'neon' ? '10,10,15' : '20,20,30'}, ${
                              t.key === 'frosted' || t.key === 'depth' || t.key === 'flat' ? '1' : '0.6'
                            })`,
                    backdropFilter: t.key === 'glass' || t.key === 'neon' || t.key === 'liquid-mesh'
                      ? `blur(${t.key === 'liquid-mesh' ? 6 : 4}px)`
                      : 'none',
                    border: t.key === 'frosted' ? 'none' : '1px solid rgba(255,255,255,0.06)',
                    boxShadow: t.key === 'depth'
                      ? '0 1px 0 rgba(255,255,255,0.03), 0 2px 6px rgba(0,0,0,0.4)'
                      : t.key === 'neon'
                        ? '0 0 6px rgba(124,58,237,0.15)'
                        : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 10,
                    color: t.key === 'paper' ? '#999' : 'rgba(255,255,255,0.3)',
                  }}
                >
                  Preview
                </div>

                {/* 选中勾 */}
                {isActive && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 6,
                      right: 6,
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      background: 'var(--brand-accent)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 12,
                      color: 'var(--text-inverse)',
                      fontWeight: 700,
                      boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                    }}
                  >
                    ✓
                  </div>
                )}
              </div>

              {/* 名称 + 描述 */}
              <div style={{ padding: '10px 12px' }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: isActive ? 'var(--brand-accent)' : 'var(--text-primary)',
                    marginBottom: 2,
                  }}
                >
                  {t.name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--surface-fog)', lineHeight: 1.4 }}>
                  {t.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 霓虹质感专属 — 品牌色切换 */}
      {activeTexture === 'neon' && (
        <div style={{ marginTop: 20, padding: '14px 16px', borderRadius: 8, background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <ThunderboltOutlined style={{ color: '#9b59b6', fontSize: 16 }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>霓虹品牌色</span>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {[
              { key: 'purple', color: '#7C3AED', label: '电光紫', desc: '经典赛博' },
              { key: 'cyan', color: '#06B6D4', label: '电光青', desc: '冷调科技' },
            ].map(acc => {
              const isAccActive = neonAccent === acc.key;
              return (
                <div
                  key={acc.key}
                  onClick={() => {
                    setNeonAccent(acc.key);
                    switchNeonAccent(acc.key);
                    syncUserThemeToServer();
                  }}
                  style={{
                    cursor: 'pointer',
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: isAccActive
                      ? `2px solid ${acc.color}`
                      : '1px solid rgba(255,255,255,0.08)',
                    background: isAccActive
                      ? `${acc.color}15`
                      : 'transparent',
                    transition: 'all 200ms',
                    textAlign: 'center',
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      background: acc.color,
                      margin: '0 auto 6px',
                      boxShadow: isAccActive ? `0 0 12px ${acc.color}60` : 'none',
                    }}
                  />
                  <div style={{ fontSize: 12, fontWeight: 600, color: acc.color }}>{acc.label}</div>
                  <div style={{ fontSize: 10, color: 'var(--surface-fog)' }}>{acc.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );

  const policyTab = (
    <Card className="glass-card">
      <div style={{ maxHeight: 'calc(100vh - 240px)', overflow: 'auto', paddingRight: 8 }}>
        <Title level={4}>隐私政策</Title>
        <Paragraph type="secondary">更新日期：2026年8月13日</Paragraph>
        <Paragraph>
          动态数据登记系统（以下简称"本软件"）由个人开发者（以下简称"我方"或"我们"）开发并发布。
          我们深知个人信息对您的重要性，并承诺严格遵守《中华人民共和国个人信息保护法》《中华人民共和国数据安全法》
          《中华人民共和国网络安全法》等相关法律法规，切实保护您的隐私。本隐私政策旨在向您清晰、透明地说明本软件在
          数据收集、使用、存储和保护方面的做法。请您在使用本软件前仔细阅读本隐私政策。
        </Paragraph>

        <Title level={5}>一、我们收集哪些信息</Title>
        <Paragraph>1.1 <strong>我们不收集任何信息。</strong>本软件完全运行于您的本地设备，不会以任何方式主动收集、上传或存储您的个人信息或业务数据。</Paragraph>
        <Paragraph>1.2 您录入的全部数据（包括但不限于字段定义、业务记录、操作日志、系统配置等）<strong>仅存储在您本地设备中</strong>，由您自行管理和维护，我们无法访问、查看或获取这些数据。</Paragraph>
        <Paragraph>1.3 本软件不涉及任何形式的用户画像、行为追踪、数据分析或自动化决策服务。</Paragraph>

        <Title level={5}>二、Cookie 与本地存储</Title>
        <Paragraph>2.1 本软件为桌面应用程序，不使用浏览器 Cookie 或类似的网络追踪技术。</Paragraph>
        <Paragraph>2.2 如您通过浏览器访问本软件的 Web 界面，浏览器可能使用 <code>localStorage</code> / <code>sessionStorage</code> 存储您的登录凭证和界面偏好设置（如主题、布局等），这些数据仅存在于您的浏览器中，不会被发送至任何远程服务器。</Paragraph>
        <Paragraph>2.3 您可以通过浏览器设置清除这些本地存储数据，但清除后可能需要重新登录或重新配置偏好设置。</Paragraph>

        <Title level={5}>三、数据如何存储与保护</Title>
        <Paragraph>3.1 <strong>本地存储：</strong>所有业务数据存储在您本地设备的数据库文件（SQLite）中，不经过任何云端服务器或第三方中间节点。</Paragraph>
        <Paragraph>3.2 <strong>密码保护：</strong>您的账户密码采用 PBKDF2-SHA256 算法进行加盐哈希处理后存储，任何人（包括我们）均无法逆向还原您的原始密码。</Paragraph>
        <Paragraph>3.3 <strong>无远程访问：</strong>本软件不设置任何形式的远程访问通道、后门接口或远程控制功能。</Paragraph>
        <Paragraph>3.4 <strong>您的责任：</strong>您应对自身设备的物理安全和网络安全负责，包括但不限于设置设备密码、启用防火墙、安装杀毒软件、定期更新操作系统等。如您将数据库文件存放在共享设备或云端存储中，应自行承担相应的安全风险。</Paragraph>

        <Title level={5}>四、网络通信说明</Title>
        <Paragraph>4.1 本软件的<strong>核心功能无需联网</strong>即可正常运行。</Paragraph>
        <Paragraph>4.2 仅在以下场景中，本软件可能发起网络请求：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 您主动点击"检查更新"按钮，此时本软件仅查询版本号信息，不传输任何个人数据；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 您主动使用需要网络的扩展功能模块（如有）；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 您主动发起 AI 数据分析时，本软件会将相关数据摘要发送至您自行配置的 AI 模型服务商（如 DeepSeek、OpenAI、通义千问等）进行智能分析。</Paragraph>
        <Paragraph>4.3 本软件不存在任何自动化的后台数据传输、云端同步或向第三方服务器上报信息的行为。</Paragraph>

        <Title level={5}>五、AI 分析功能说明</Title>
        <Paragraph>5.1 AI 分析为可选功能，需您在设置中自行配置 AI 服务商的 API Key 后启用。</Paragraph>
        <Paragraph>5.2 使用 AI 分析时，仅当您主动发起分析请求，本软件才会将相关数据摘要发送至您配置的 AI 服务商，用于生成分析报告和对话回复。</Paragraph>
        <Paragraph>5.3 <strong>数据范围受权限控制：</strong>员工账号仅能分析自己创建的数据；HR 与管理员账号可分析全量数据。不同账号的数据可见范围与其在系统中的权限保持一致。</Paragraph>
        <Paragraph>5.4 <strong>记录按账号隔离：</strong>分析报告与对话记录仅保存在本机数据库中，并按账号隔离存储，不同账号之间的记录互不可见。您可随时在 AI 分析页面清除全部分析记录。</Paragraph>
        <Paragraph>5.5 由于 AI 服务商为第三方服务，其数据处理行为受该服务商自身隐私政策的约束，建议您在使用前查阅相应服务商的隐私条款。</Paragraph>

        <Title level={5}>六、第三方服务</Title>
        <Paragraph>6.1 本软件<strong>不集成任何第三方 SDK</strong>、追踪代码、广告组件或统计分析工具。</Paragraph>
        <Paragraph>6.2 我们不会将您的数据出售、出租、共享或披露给任何第三方。</Paragraph>
        <Paragraph>6.3 在法律法规要求或司法机关依法指令的情况下，我们可能需配合提供必要信息，但此情形仅适用于法律明确要求的范围，且需合法的法律文书为前提。由于我们并不掌握任何用户数据，此种情况下我们无法提供实质性信息。</Paragraph>

        <Title level={5}>七、您的权利</Title>
        <Paragraph>作为数据的完全控制者，您享有以下权利：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>查阅权：</strong>您可以随时查看本软件中存储的所有数据；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>修改权：</strong>您可以对任何数据进行新增、编辑或删除操作；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>导出权：</strong>您可以通过内置的导出功能将数据导出为 Excel 等格式；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>备份权：</strong>您可以通过"备份恢复"功能对数据库进行完整备份和恢复；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>删除权：</strong>您可以通过"重置数据库"功能清空所有业务数据，或直接删除数据库文件；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>卸载权：</strong>您可以随时卸载本软件，卸载后本地数据文件不会自动删除，由您自行决定保留或删除。</Paragraph>
        <Paragraph>建议您定期备份数据库文件，以防硬件故障、误操作或其他意外情况导致数据丢失。</Paragraph>

        <Title level={5}>八、数据保留与销毁</Title>
        <Paragraph>8.1 您的数据保留期限完全由您自行决定，本软件不会设置数据自动过期或自动删除机制。</Paragraph>
        <Paragraph>8.2 如您决定不再使用本软件，可通过卸载程序并手动删除数据库文件来永久销毁所有数据。</Paragraph>
        <Paragraph>8.3 数据库文件默认存储在本软件的安装目录或您指定的数据目录中，请确认您已找到并删除相关文件。</Paragraph>

        <Title level={5}>九、未成年人保护</Title>
        <Paragraph>9.1 本软件为通用生产力工具，不专门面向未成年人提供特定服务。</Paragraph>
        <Paragraph>9.2 如您为未满 14 周岁的未成年人，请在您的父母或其他监护人的陪同下阅读本隐私政策，并在征得监护人同意后使用本软件。</Paragraph>
        <Paragraph>9.3 如监护人发现未成年人未经同意向我们提供了个人信息，可通过下方联系方式通知我们，以便采取相应措施。但由于我们不收集任何用户数据，此种风险极低。</Paragraph>

        <Title level={5}>十、隐私保护建议</Title>
        <Paragraph>为最大程度保护您的数据隐私，我们建议：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>1. 请勿将包含敏感信息的数据库文件存放在公共设备、共享文件夹或未加密的云端存储中；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>2. 如涉及高度敏感信息（如身份证号、银行账户、健康信息等），建议对数据库文件进行额外加密；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>3. 为操作系统设置强密码并定期更换，启用屏幕锁，防止未经授权的物理访问；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>4. 如发现数据库文件被非授权访问或泄露，应立即停止使用、删除相关文件，并评估潜在影响。</Paragraph>

        <Title level={5}>十一、政策更新</Title>
        <Paragraph>11.1 本隐私政策可能根据法律法规变化、软件功能更新或行业标准的演进适时调整。</Paragraph>
        <Paragraph>11.2 更新后的隐私政策将在软件更新公告、设置页面的"法律信息"标签页中同步公示。</Paragraph>
        <Paragraph>11.3 重大变更（如涉及数据处理方式的实质性改变）将以弹窗或公告形式通知您。</Paragraph>
        <Paragraph>11.4 您继续使用本软件即视为已阅读并接受更新后的隐私政策。如您不同意修订后的条款，应停止使用本软件并卸载。</Paragraph>

        <Title level={5}>十二、联系方式</Title>
        <Paragraph>如您对本隐私政策有任何疑问、意见或建议，或需要行使您的相关权利，欢迎通过以下方式联系我们：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>电子邮件：</strong>请通过本软件发布页面或官方渠道获取开发者联系邮箱。</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>反馈渠道：</strong>您亦可在软件的设置页面或发布平台的评论区提交反馈。</Paragraph>
        <Paragraph>我们将在收到您的反馈后尽快予以回复。</Paragraph>

        <Title level={5}>十三、法律适用</Title>
        <Paragraph>13.1 本隐私政策的订立、执行、解释及争议解决均适用中华人民共和国法律。</Paragraph>
        <Paragraph>13.2 如本隐私政策的任何条款与适用法律相抵触，该条款应视为按法律规定重新解释，其他条款的效力不受影响。</Paragraph>
        <Paragraph>13.3 如有争议，双方应首先通过友好协商解决；协商不成的，任何一方可向开发者所在地有管辖权的人民法院提起诉讼。</Paragraph>

        <Divider />

        <Title level={4}>用户协议</Title>
        <Paragraph type="secondary">更新日期：2026年8月13日</Paragraph>
        <Paragraph>
          欢迎使用"动态数据登记系统"（以下简称"本软件"）。本软件由个人开发者（以下简称"我方"或"我们"）开发并发布。
          在安装、复制或使用本软件前，请您仔细阅读本用户协议（以下简称"本协议"）。
          <strong>一旦您安装、复制或以任何方式使用本软件，即表示您已充分阅读、理解并同意接受本协议所有条款的约束。</strong>
          如您不同意本协议的任何条款，请勿安装或使用本软件，并立即删除与本软件相关的所有文件。
        </Paragraph>

        <Title level={5}>一、定义</Title>
        <Paragraph>1.1 <strong>"本软件"</strong>：指"动态数据登记系统"及其所有相关组件，包括但不限于可执行程序、源代码、文档、配置文件及随附资源。</Paragraph>
        <Paragraph>1.2 <strong>"用户"或"您"</strong>：指安装、使用本软件的自然人、法人或其他组织。</Paragraph>
        <Paragraph>1.3 <strong>"我方"或"我们"</strong>：指本软件的开发者及版权所有者。</Paragraph>

        <Title level={5}>二、许可授权</Title>
        <Paragraph>2.1 <strong>免费许可：</strong>我们授予您一项非独占、不可转让、不可分许可的有限许可，允许您在本协议条款约束下免费安装和使用本软件。</Paragraph>
        <Paragraph>2.2 <strong>使用范围：</strong>您可在合法范围内将本软件用于个人或商业用途，包括但不限于企业内部数据管理、信息登记与查询、项目台账维护等场景。</Paragraph>
        <Paragraph>2.3 <strong>许可限制：</strong>除本协议明确授予的权利外，您不享有本软件的其他任何权利。本许可是对使用权的许可，而非所有权的出售。</Paragraph>

        <Title level={5}>三、使用限制</Title>
        <Paragraph>3.1 您承诺不会将本软件用于以下任何用途：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（1）违反中华人民共和国法律法规或您所在地法律法规的行为；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（2）存储、传播违法信息、淫秽色情内容或危害国家安全的信息；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（3）侵犯他人知识产权、隐私权、名誉权或其他合法权益；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（4）实施欺诈、诈骗、非法集资等违法犯罪活动；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（5）干扰、破坏或损害网络、服务器、计算机系统的正常运行。</Paragraph>
        <Paragraph>3.2 未经我们明确书面许可，您不得：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（1）对本软件进行整体或部分的反向工程、反编译、反汇编或提取源代码（我们主动公开提供的源代码除外）；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（2）移除、修改或遮挡本软件中包含的任何版权声明、商标标识或其他知识产权声明；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（3）将本软件或其修改版本作为独立产品进行重新分发、销售、出租、许可或转让。</Paragraph>

        <Title level={5}>四、知识产权</Title>
        <Paragraph>4.1 本软件的全部知识产权（包括但不限于计算机软件著作权、界面设计、图标、文档及随附材料）归我方所有，受中华人民共和国《著作权法》《计算机软件保护条例》等相关法律法规保护。</Paragraph>
        <Paragraph>4.2 本软件的名称、标识等均为我方的知识产权，未经授权不得以任何方式使用。</Paragraph>
        <Paragraph>4.3 您在使用本软件过程中产生的业务数据，其所有权归您所有。我们对您的数据不主张任何权利。</Paragraph>
        <Paragraph>4.4 如您基于本软件开放的部分进行学习、参考或二次开发，衍生成果中涉及您原创部分的知识产权归您所有，但您应保留本软件的原始版权声明，且不得将二次开发的成果用于与本软件构成直接竞争的商业目的。</Paragraph>

        <Title level={5}>五、数据安全</Title>
        <Paragraph>5.1 <strong>数据归属：</strong>您在使用本软件过程中录入、生成的全部数据（包括但不限于字段定义、业务记录、操作日志、系统配置等）均存储在您的本地设备中，由您完全掌控。我们不收集、不上传、不存储您的任何数据。</Paragraph>
        <Paragraph>5.2 <strong>您的责任：</strong>您对数据的完整性、安全性和合规性承担全部责任。您应自行采取合理措施保护数据安全，包括但不限于：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 定期使用本软件内置的备份功能对数据库进行备份；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 为操作系统和您的设备设置访问密码或生物识别锁；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 安装并及时更新杀毒软件和防火墙；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 避免在公共计算机或不受信任的设备上使用本软件。</Paragraph>
        <Paragraph>5.3 因以下情形导致的数据丢失、泄露或损坏，我方不承担责任：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（1）您的设备硬件故障、操作系统崩溃或存储介质损坏；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（2）您的误操作（包括但不限于误删除、未备份、强制关闭程序等）；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（3）病毒、木马、勒索软件或其他恶意程序的攻击；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（4）第三方的未授权访问（包括物理访问和网络入侵）；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（5）不可抗力事件（包括但不限于自然灾害、战争、电力中断等）。</Paragraph>

        <Title level={5}>六、账号与权限</Title>
        <Paragraph>6.1 本软件内置三种账号角色：<strong>员工（employee）、人事（hr）、管理员（boss）</strong>，各角色拥有不同权限：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- <strong>员工：</strong>仅可查看与录入自己创建的数据，数据管理页为只读权限，无法修改或删除他人数据；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- <strong>人事（HR）：</strong>可查看全量数据；其删除操作需提交审核，由管理员批准后才会真正执行；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- <strong>管理员：</strong>拥有全部管理权限，并负责审核所有待审核的操作。</Paragraph>
        <Paragraph>6.2 您应妥善保管自己的账号与密码，不得将账号出借或转让给他人。因账号保管不善导致的数据泄露或误操作，由账号持有人自行承担相应责任。</Paragraph>

        <Title level={5}>七、AI 分析功能</Title>
        <Paragraph>7.1 AI 分析为本软件的可选扩展功能，需您自行配置 AI 模型服务商的 API Key 后方可使用。</Paragraph>
        <Paragraph>7.2 使用 AI 分析即表示您知悉并同意：为完成分析，本软件会将<strong>相关数据摘要</strong>发送至您所配置的第三方 AI 服务商。涉及敏感、机密或受法律保护的信息，请谨慎使用本功能。</Paragraph>
        <Paragraph>7.3 <strong>数据范围：</strong>AI 可分析的数据范围与您的账号权限一致——员工仅能分析自己创建的数据，HR 与管理员可分析全量数据。</Paragraph>
        <Paragraph>7.4 <strong>记录隔离：</strong>分析报告与对话记录按账号隔离存储于本机，不同账号之间互不可见，您可随时清除。</Paragraph>
        <Paragraph>7.5 因第三方 AI 服务商自身原因（包括但不限于服务中断、响应内容偏差、数据保留政策）产生的问题，我方不承担相关责任。</Paragraph>

        <Title level={5}>八、免责声明</Title>
        <Paragraph>8.1 本软件按<strong>"现状"（AS IS）</strong>提供，不附带任何形式的明示或默示担保，包括但不限于对适销性、特定用途适用性、准确性、可靠性或不侵权的担保。</Paragraph>
        <Paragraph>8.2 我们不保证本软件完全无错误、无缺陷或不中断运行。您应自行承担使用本软件的全部风险。</Paragraph>
        <Paragraph>8.3 我们不保证本软件满足您的全部需求，您应自行评估本软件是否适合您的特定使用场景。</Paragraph>
        <Paragraph>8.4 如您所在司法管辖区不允许排除默示担保，则上述免责声明的部分内容可能对您不适用。</Paragraph>

        <Title level={5}>九、责任限制</Title>
        <Paragraph>9.1 在法律允许的最大范围内，我方不对因使用或无法使用本软件而产生的任何直接、间接、附带、特殊、惩罚性或后果性损失承担责任，包括但不限于：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 数据丢失或损坏；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 业务中断或利润损失；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 商誉损失或声誉损害；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>- 替代产品或服务的采购成本。</Paragraph>
        <Paragraph>9.2 即使我方已被告知此类损失的可能性，上述责任限制仍然适用。</Paragraph>
        <Paragraph>9.3 如适用法律不允许对某些类型的损失限制责任，则上述限制的部分内容可能对您不适用。在此情况下，我方的责任应在法律允许的最小范围内确定。</Paragraph>

        <Title level={5}>十、赔偿</Title>
        <Paragraph>您同意赔偿、辩护并使我方免受因以下原因引起的任何第三方索赔、诉讼、损害赔偿、损失、费用或开支（包括合理的律师费）：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（1）您违反本协议的任何条款；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（2）您使用本软件的行为侵犯了任何第三方的合法权益；</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}>（3）您存储于本软件中的数据内容违反法律法规或侵犯第三方权利。</Paragraph>

        <Title level={5}>十一、软件更新</Title>
        <Paragraph>11.1 我们保留随时发布本软件更新版本的权利，更新可能包括功能增强、性能优化、安全修复、错误更正或界面调整。</Paragraph>
        <Paragraph>11.2 我们保留停止维护或终止本软件后续版本开发的权利，但不会主动删除您设备上已安装的版本。</Paragraph>
        <Paragraph>11.3 您可选择安装更新版本或继续使用当前版本。我们不承诺对旧版本提供持续的技术支持或安全补丁。</Paragraph>
        <Paragraph>11.4 本协议适用于本软件的所有版本，除非新版本附带了单独的协议。</Paragraph>

        <Title level={5}>十二、协议终止</Title>
        <Paragraph>12.1 本协议自您首次使用本软件之日起生效，持续有效直至终止。</Paragraph>
        <Paragraph>12.2 您可以通过卸载本软件并永久删除与本软件相关的所有文件来随时终止本协议。</Paragraph>
        <Paragraph>12.3 如您违反本协议的任何条款，我方保留立即终止本协议的权利。终止后，您应立即停止使用本软件，卸载并删除所有相关文件。</Paragraph>
        <Paragraph>12.4 协议终止不影响双方在终止前已产生的权利义务，也不影响依其性质应在终止后继续有效的条款（包括但不限于知识产权、免责声明、责任限制等条款）。</Paragraph>

        <Title level={5}>十三、协议修改</Title>
        <Paragraph>13.1 我们保留随时修改或更新本协议的权利。</Paragraph>
        <Paragraph>13.2 修改后的协议将在软件更新公告、设置页面的"法律信息"标签页中同步公示。重大修改可能以弹窗或其他显著方式通知您。</Paragraph>
        <Paragraph>13.3 您在协议修改后继续使用本软件，即视为您已接受修改后的条款。如您不同意修改后的条款，应停止使用本软件并卸载。</Paragraph>

        <Title level={5}>十四、完整协议</Title>
        <Paragraph>14.1 本协议（连同随附的隐私政策）构成您与我方之间关于本软件的完整协议，取代之前所有口头或书面的沟通、陈述、谈判或协议。</Paragraph>
        <Paragraph>14.2 如本协议的任何条款被有管辖权的法院认定为无效或不可执行，该条款应在法律允许的最大范围内执行，且其他条款的效力不受影响。</Paragraph>
        <Paragraph>14.3 我方未能行使或执行本协议中的任何权利或条款，不应视为对该权利或条款的放弃。</Paragraph>

        <Title level={5}>十五、法律适用与争议解决</Title>
        <Paragraph>15.1 本协议的订立、效力、解释、履行及争议解决均适用中华人民共和国法律。</Paragraph>
        <Paragraph>15.2 您与我方之间因本协议产生的任何争议或纠纷，双方应首先通过友好协商解决。</Paragraph>
        <Paragraph>15.3 如协商不成，任何一方可将争议提交至开发者所在地有管辖权的人民法院通过诉讼解决。</Paragraph>

        <Title level={5}>十六、联系方式</Title>
        <Paragraph>如您对本协议有任何疑问、意见或需要法律方面的澄清，欢迎通过以下方式联系我们：</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>电子邮件：</strong>请通过本软件发布页面或官方渠道获取开发者联系邮箱。</Paragraph>
        <Paragraph style={{ paddingLeft: 16 }}><strong>在线反馈：</strong>您亦可在软件的设置页面或发布平台的评论区提交反馈。</Paragraph>
      </div>
    </Card>
  );

  const dbTab = (
    <Card className="glass-card">
      <Spin spinning={isLoading}>
        <Descriptions title="当前状态" bordered size="small" column={{ xs: 1, sm: 2 }} style={{ marginBottom: 24 }}>
          <Descriptions.Item label="数据库引擎"><Tag color={settings?.db_engine === 'mysql' ? 'blue' : 'green'}>{settings?.db_engine === 'mysql' ? 'MySQL' : 'SQLite'}</Tag></Descriptions.Item>
          {settings?.db_engine === 'mysql' && (<>
            <Descriptions.Item label="MySQL 主机">{settings.mysql_host ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="MySQL 端口">{settings.mysql_port ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="数据库名">{settings.mysql_database ?? '-'}</Descriptions.Item>
          </>)}
        </Descriptions>
        <Divider /><Title level={5} style={{ marginBottom: 16 }}>数据库引擎设置</Title>
        <Alert message="切换数据库引擎需要重启后端服务后才能生效" type="warning" showIcon style={{ marginBottom: 16 }} />
        <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 560 }}>
          <Form.Item label="数据库引擎">
            <Select<DBEngine> value={selectedEngine} onChange={(val) => { setSelectedEngine(val); form.setFieldValue('db_engine', val); }}
              options={[{ label: 'SQLite (本地文件数据库)', value: 'sqlite' }, { label: 'MySQL (远程数据库)', value: 'mysql' }]} />
          </Form.Item>
          {selectedEngine === 'mysql' && (<>
            <Form.Item name="mysql_host" label="MySQL 主机地址" rules={[{ required: true, message: '请输入主机地址' }]}><Input placeholder="localhost" /></Form.Item>
            <Form.Item name="mysql_port" label="MySQL 端口" rules={[{ required: true, message: '请输入端口号' }]}><InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="3306" /></Form.Item>
            <Form.Item name="mysql_user" label="MySQL 用户名" rules={[{ required: true, message: '请输入用户名' }]}><Input placeholder="root" /></Form.Item>
            <Form.Item name="mysql_password" label="MySQL 密码"><Input.Password placeholder="请输入密码（可为空）" /></Form.Item>
            <Form.Item name="mysql_database" label="数据库名" rules={[{ required: true, message: '请输入数据库名' }]}><Input placeholder="app_db" /></Form.Item>
            <Form.Item><Button icon={<LinkOutlined />} onClick={handleTestMysql} loading={testingMysql} style={{ marginRight: 12 }}>测试连接</Button><Text type="secondary">测试前请确保 MySQL 服务已启动</Text></Form.Item>
          </>)}
          <Form.Item><Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={updateMutation.isPending} className="gradient-bg" style={{ border: 'none' }}>保存设置</Button></Form.Item>
        </Form>
      </Spin>
    </Card>
  );

  return (
    <>
      {contextHolder}
      <Card className="glass-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <Title level={4} style={{ margin: 0 }}>系统设置</Title>
          <Button icon={<ReloadOutlined />} onClick={() => queryClient.invalidateQueries({ queryKey: ['settings'] })}>刷新</Button>
        </div>
      </Card>
      <Tabs defaultActiveKey="db" items={[
        { key: 'db', label: '数据库', children: dbTab },
        { key: 'texture', label: '背景质感', children: textureTab },
        { key: 'theme', label: '自定义配色', children: themeTab },
        { key: 'policy', label: '协议与隐私', children: policyTab },
      ]} />
    </>
  );
}

export default Settings;