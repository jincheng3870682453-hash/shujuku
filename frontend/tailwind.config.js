/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    screens: {
      'sm': '640px',
      'md': '1024px',
      'lg': '1440px',
    },
    extend: {
      colors: {
        // Surface 层次
        surface: {
          root:      '#0d0d0d',
          ground:    '#111111',
          sidebar:   '#0f0f0f',
          card:      '#1a1a1a',
          elevated:  '#1f1f1f',
          hover:     '#252525',
          active:    '#2a2a2a',
        },
        // 边框
        border: {
          DEFAULT:  '#262626',
          subtle:   '#1f1f1f',
          strong:   '#333333',
          accent:   '#5e6ad2',
        },
        // 文字
        text: {
          primary:    '#ededed',
          secondary:  '#888888',
          tertiary:   '#555555',
          disabled:   '#444444',
          inverse:    '#0d0d0d',
        },
        // 品牌色
        accent: {
          DEFAULT:   '#5e6ad2',
          hover:     '#7078e0',
          active:    '#4f5bc0',
          subtle:    'rgba(94, 106, 210, 0.12)',
          ghost:     'rgba(94, 106, 210, 0.06)',
        },
        // 语义色
        success: {
          DEFAULT:   '#0eb478',
          bg:        'rgba(14, 180, 120, 0.1)',
        },
        warning: {
          DEFAULT:   '#f5a623',
          bg:        'rgba(245, 166, 35, 0.1)',
        },
        error: {
          DEFAULT:   '#e5484d',
          bg:        'rgba(229, 72, 77, 0.1)',
        },
        info: {
          DEFAULT:   '#3b82f6',
          bg:        'rgba(59, 130, 246, 0.1)',
        },
      },
      fontFamily: {
        sans: ["'Inter'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", "'PingFang SC'", "'Microsoft YaHei'", 'sans-serif'],
        mono: ["'JetBrains Mono'", "'Fira Code'", "'Cascadia Code'", 'monospace'],
      },
      fontSize: {
        'xs':    ['11px', { lineHeight: '1.5' }],
        'sm':    ['12px', { lineHeight: '1.5' }],
        'base':  ['13px', { lineHeight: '1.5' }],
        'md':    ['14px', { lineHeight: '1.5' }],
        'lg':    ['16px', { lineHeight: '1.5' }],
        'xl':    ['20px', { lineHeight: '1.25', letterSpacing: '-0.5px' }],
        '2xl':   ['24px', { lineHeight: '1.25', letterSpacing: '-0.5px' }],
        '3xl':   ['30px', { lineHeight: '1.25', letterSpacing: '-0.5px' }],
      },
      fontWeight: {
        normal: '400',
        medium: '500',
        semibold: '600',
      },
      borderRadius: {
        sm:    '4px',
        md:    '6px',
        lg:    '8px',
        xl:    '10px',
        '2xl': '14px',
        full:  '9999px',
      },
      boxShadow: {
        xs:    '0 0 0 1px rgba(255,255,255,0.04)',
        sm:    '0 1px 2px rgba(0,0,0,0.4)',
        md:    '0 4px 12px rgba(0,0,0,0.5)',
        lg:    '0 8px 24px rgba(0,0,0,0.6)',
        xl:    '0 16px 48px rgba(0,0,0,0.7)',
      },
      spacing: {
        '1':    '4px',
        '2':    '8px',
        '3':    '12px',
        '4':    '16px',
        '5':    '20px',
        '6':    '24px',
        '8':    '32px',
        '10':   '40px',
        '12':   '48px',
        '16':   '64px',
      },
      transitionDuration: {
        fast:  '150ms',
        base:  '200ms',
        slow:  '300ms',
      },
      transitionTimingFunction: {
        DEFAULT: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 与 Ant Design 共存，禁止 Tailwind 重置
  },
}
