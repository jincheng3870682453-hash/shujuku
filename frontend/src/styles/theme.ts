import type { ThemeConfig } from 'antd';

/**
 * Linear-inspired Dark Theme for Ant Design 5
 * 精确到像素的暗色主题 Token，对标 Linear「午夜精密仪器」设计系统
 */
const darkTheme: ThemeConfig = {
  token: {
    // ── 色彩 ──
    colorPrimary: '#5e6ad2',
    colorInfo: '#02b8cc',
    colorSuccess: '#27a644',
    colorWarning: '#f0a020',
    colorError: '#eb5757',
    colorTextBase: '#d0d6e0',
    colorBgBase: '#08090a',

    // ── 排版 ──
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
    fontFamilyCode: "'JetBrains Mono', 'SF Mono', 'Fira Code', Consolas, monospace",
    fontSize: 14,
    fontSizeHeading1: 28,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 17,
    fontSizeHeading5: 16,
    lineHeight: 1.5,

    // ── 形状 ──
    borderRadius: 6,
    borderRadiusLG: 12,
    borderRadiusSM: 4,
    borderRadiusXS: 2,
    wireframe: false,

    // ── 尺寸 ──
    controlHeight: 34,
    controlHeightLG: 42,
    controlHeightSM: 28,
    padding: 16,
    paddingXS: 8,
    paddingSM: 12,
    paddingLG: 24,
    paddingContentHorizontal: 16,
    paddingContentHorizontalLG: 24,
    paddingContentVertical: 12,
    paddingContentVerticalLG: 20,

    // ── 间距 ──
    marginXS: 4,
    marginSM: 8,
    margin: 16,
    marginMD: 20,
    marginLG: 24,
    marginXL: 32,
    marginXXL: 48,

    // ── 线条 ──
    lineWidth: 1,
    lineType: 'solid',
    lineWidthBold: 2,
  },

  components: {
    Layout: {
      bodyBg: '#08090a',
      headerBg: '#08090a',
      siderBg: '#0f1011',
      triggerBg: '#161718',
      triggerColor: '#8a8f98',
    },

    Menu: {
      darkItemBg: 'transparent',
      darkItemColor: '#8a8f98',
      darkItemHoverBg: 'rgba(94, 106, 210, 0.08)',
      darkItemHoverColor: '#d0d6e0',
      darkItemSelectedBg: 'rgba(94, 106, 210, 0.15)',
      darkItemSelectedColor: '#5e6ad2',
      darkSubMenuItemBg: 'transparent',
      itemBorderRadius: 8,
      itemMarginInline: 8,
      itemHeight: 36,
      iconSize: 18,
      collapsedIconSize: 20,
    },

    Table: {
      headerBg: '#0f1011',
      headerColor: '#8a8f98',
      rowHoverBg: 'rgba(94, 106, 210, 0.04)',
      rowSelectedBg: 'rgba(94, 106, 210, 0.08)',
      rowSelectedHoverBg: 'rgba(94, 106, 210, 0.12)',
      borderColor: '#23252a',
      cellPaddingBlock: 10,
      cellPaddingInline: 16,
      headerBorderRadius: 10,
    },

    Card: {
      colorBgContainer: '#0f1011',
      borderRadiusLG: 12,
      paddingLG: 24,
      colorBorderSecondary: '#23252a',
    },

    Button: {
      borderRadius: 6,
      borderRadiusLG: 8,
      borderRadiusSM: 4,
      controlHeight: 34,
      controlHeightLG: 42,
      controlHeightSM: 28,
      paddingInline: 16,
      paddingInlineLG: 20,
      paddingInlineSM: 12,
      colorPrimaryHover: '#7378e0',
      colorPrimaryActive: '#4a54c0',
      defaultBg: '#0f1011',
      defaultBorderColor: '#383b3f',
      defaultColor: '#d0d6e0',
      defaultHoverBg: '#161718',
      defaultHoverBorderColor: '#62666d',
      defaultHoverColor: '#e5e5e6',
      defaultActiveBg: '#23252a',
      defaultActiveBorderColor: '#62666d',
      defaultActiveColor: '#ffffff',
      fontWeight: 500,
      textHoverBg: 'rgba(94, 106, 210, 0.08)',
    },

    Input: {
      borderRadius: 6,
      borderRadiusLG: 8,
      borderRadiusSM: 4,
      controlHeight: 34,
      controlHeightLG: 42,
      controlHeightSM: 28,
      colorBgContainer: '#0f1011',
      colorBorder: '#383b3f',
      colorTextPlaceholder: '#62666d',
      hoverBorderColor: '#62666d',
      activeBorderColor: '#5e6ad2',
      activeShadow: '0 0 0 2px rgba(94, 106, 210, 0.15)',
      colorIcon: '#62666d',
      colorIconHover: '#8a8f98',
      paddingInline: 12,
    },

    Select: {
      borderRadius: 6,
      borderRadiusLG: 8,
      borderRadiusSM: 4,
      controlHeight: 34,
      colorBgContainer: '#0f1011',
      colorBorder: '#383b3f',
      colorTextPlaceholder: '#62666d',
      optionSelectedBg: 'rgba(94, 106, 210, 0.15)',
      optionSelectedColor: '#5e6ad2',
      multipleItemBg: 'rgba(94, 106, 210, 0.1)',
      multipleItemBorderColor: 'rgba(94, 106, 210, 0.2)',
    },

    Modal: {
      borderRadiusLG: 14,
      colorBgElevated: '#0f1011',
      colorBgMask: 'rgba(0, 0, 0, 0.65)',
      paddingContentHorizontal: 24,
      paddingMD: 24,
      titleFontSize: 18,
      titleLineHeight: 1.4,
    },

    Tooltip: {
      colorBgSpotlight: '#161718',
      colorTextLightSolid: '#d0d6e0',
      borderRadius: 6,
      paddingSM: 8,
      padding: 8,
    },

    Dropdown: {
      colorBgElevated: '#0f1011',
      borderRadiusLG: 10,
      controlItemBgHover: 'rgba(94, 106, 210, 0.08)',
      paddingBlock: 4,
    },

    Tag: {
      borderRadiusSM: 4,
      defaultBg: 'rgba(94, 106, 210, 0.08)',
      defaultColor: '#5e6ad2',
    },

    Badge: {
      borderRadius: 4,
      colorBgContainer: '#eb5757',
      fontSize: 11,
    },

    Tabs: {
      colorBorderSecondary: '#23252a',
      itemSelectedColor: '#5e6ad2',
      itemHoverColor: '#d0d6e0',
      inkBarColor: '#5e6ad2',
      titleFontSize: 14,
    },

    Switch: {
      colorPrimary: '#5e6ad2',
      colorPrimaryHover: '#7378e0',
      handleBg: '#ffffff',
      colorTextQuaternary: '#383b3f',
      colorTextTertiary: '#23252a',
    },

    Breadcrumb: {
      lastItemColor: '#d0d6e0',
      linkColor: '#8a8f98',
      linkHoverColor: '#5e6ad2',
      separatorColor: '#62666d',
      fontSize: 13,
    },

    Pagination: {
      colorBgContainer: 'transparent',
      colorPrimary: '#5e6ad2',
      colorPrimaryHover: '#7378e0',
      itemActiveBg: 'rgba(94, 106, 210, 0.15)',
      itemBg: 'transparent',
      itemSize: 32,
      borderRadius: 6,
    },

    Spin: {
      colorPrimary: '#5e6ad2',
      dotSize: 28,
      dotSizeLG: 36,
      dotSizeSM: 20,
    },

    Empty: {
      colorTextDescription: '#62666d',
      colorText: '#d0d6e0',
      colorFill: '#62666d',
    },

    Alert: {
      borderRadiusLG: 10,
      colorInfoBg: 'rgba(2, 184, 204, 0.08)',
      colorInfoBorder: 'rgba(2, 184, 204, 0.2)',
      colorSuccessBg: 'rgba(39, 166, 68, 0.08)',
      colorSuccessBorder: 'rgba(39, 166, 68, 0.2)',
      colorWarningBg: 'rgba(240, 160, 32, 0.08)',
      colorWarningBorder: 'rgba(240, 160, 32, 0.2)',
      colorErrorBg: 'rgba(235, 87, 87, 0.08)',
      colorErrorBorder: 'rgba(235, 87, 87, 0.2)',
    },

    Notification: {
      borderRadiusLG: 12,
      colorBgElevated: '#0f1011',
      boxShadow: '0px 8px 24px rgba(0, 0, 0, 0.6)',
    },

    Statistic: {
      contentFontSize: 28,
      titleFontSize: 13,
    },
  },
};

export default darkTheme;
