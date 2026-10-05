import type { ThemeConfig } from 'antd';

/**
 * Ant Design 5 Theme Tokens
 * 选定方向：B · Airtable Grid View 标杆迁移
 *
 * ⚠️ 架构说明（本次重构的核心修正之一）：
 * 此前本文件是**独立的一套硬编码暗色值**，与 tokens.css / textures.css / 页面行内
 * 硬编码色值四套并行、互不通气——改 AntD token 不影响自定义组件，切质感不影响
 * AntD 组件，自定义配色写入的 --accent-default / --surface-root 甚至从未定义。
 *
 * 现在本文件与 tokens.css 共享同一套色值常量（下方 COLORS 对象），保证
 * 「改一处 → 两边同步」。COLORS 对应 tokens.css 的 L1 原始层，
 * 因此切换 data-texture 只需覆写 L1，AntD 组件与自定义组件会同步跟随。
 */

/** 与 tokens.css L1 原始层一一对应，禁止在此处另起炉灶写新色值 */
const COLORS = {
  white: '#ffffff',

  ink900: '#181d26',
  ink700: '#3d444d',
  ink500: '#5c6470',
  ink400: '#6e6e6e',

  gray025: '#fafaf8',
  gray050: '#f4f4f1',
  gray100: '#ededea',
  gray150: '#e3e3df',
  gray200: '#d8d8d3',
  gray300: '#c2c2bc',

  blue050: '#eef4fc',
  blue100: '#dbe7f8',
  blue600: '#1b61c9',
  blue700: '#17529f',

  green050: '#dcf1e3',
  green500: '#2f8f52',
  green700: '#14622f',

  amber050: '#fcefc7',
  amber500: '#c98a00',
  amber700: '#7a4e00',

  red050: '#fbe0e0',
  red500: '#c0392b',
  red600: '#b42318',
  red700: '#a12424',
} as const;

const theme: ThemeConfig = {
  token: {
    // ── 色彩：与 tokens.css L2 语义层对齐 ──
    colorPrimary: COLORS.blue600,
    colorInfo: COLORS.blue600,
    colorSuccess: COLORS.green500,
    colorWarning: COLORS.amber500,
    colorError: COLORS.red600,
    colorTextBase: COLORS.ink900,
    colorBgBase: COLORS.white,

    // ── 排版 ──
    fontFamily:
      '"Inter", "Public Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", ' +
      '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    fontFamilyCode: '"JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace',
    fontSize: 14,
    fontSizeHeading1: 28,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 17,
    fontSizeHeading5: 16,
    lineHeight: 1.6,

    // ── 形状（B 版 4 / 6 / 10）──
    borderRadius: 6,
    borderRadiusLG: 10,
    borderRadiusSM: 4,
    borderRadiusXS: 2,
    wireframe: false,

    // ── 尺寸 ──
    controlHeight: 32,
    controlHeightLG: 40,
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
      bodyBg: COLORS.gray050,
      headerBg: COLORS.white,
      siderBg: COLORS.gray025,
      triggerBg: COLORS.gray050,
      triggerColor: COLORS.ink400,
    },

    Menu: {
      itemBg: 'transparent',
      itemColor: COLORS.ink700,
      itemHoverBg: COLORS.gray050,
      itemHoverColor: COLORS.ink900,
      itemSelectedBg: COLORS.blue050,
      itemSelectedColor: COLORS.blue600,
      subMenuItemBg: 'transparent',
      itemBorderRadius: 4,
      itemMarginInline: 8,
      itemHeight: 34,
      iconSize: 16,
      collapsedIconSize: 18,
      groupTitleColor: COLORS.ink400,
      groupTitleFontSize: 11,
    },

    Table: {
      // 病灶①修复：表头不再用暗色 #0f1011，与亮色画布统一
      headerBg: COLORS.gray025,
      headerColor: COLORS.ink700,
      headerSplitColor: COLORS.gray150,
      rowHoverBg: COLORS.gray050,
      rowSelectedBg: COLORS.blue050,
      rowSelectedHoverBg: COLORS.blue050,
      borderColor: COLORS.gray150,
      cellPaddingBlock: 10,
      cellPaddingInline: 12,
      headerBorderRadius: 0,
      cellFontSize: 13,
      footerBg: COLORS.gray025,
      footerColor: COLORS.ink700,
    },

    Card: {
      colorBgContainer: COLORS.white,
      borderRadiusLG: 10,
      paddingLG: 24,
      colorBorderSecondary: COLORS.gray150,
      headerBg: 'transparent',
      headerFontSize: 15,
    },

    Button: {
      borderRadius: 6,
      borderRadiusLG: 6,
      borderRadiusSM: 4,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 28,
      paddingInline: 12,
      paddingInlineLG: 16,
      paddingInlineSM: 8,
      colorPrimaryHover: COLORS.blue700,
      colorPrimaryActive: COLORS.blue700,
      defaultBg: COLORS.white,
      defaultBorderColor: COLORS.gray200,
      defaultColor: COLORS.ink700,
      defaultHoverBg: COLORS.gray050,
      defaultHoverBorderColor: COLORS.gray300,
      defaultHoverColor: COLORS.ink900,
      defaultActiveBg: COLORS.gray100,
      defaultActiveBorderColor: COLORS.gray300,
      defaultActiveColor: COLORS.ink900,
      textHoverBg: COLORS.gray050,
      fontWeight: 500,
    },

    Input: {
      borderRadius: 6,
      borderRadiusLG: 6,
      borderRadiusSM: 4,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 28,
      colorBgContainer: COLORS.white,
      colorBorder: COLORS.gray200,
      colorTextPlaceholder: COLORS.ink400,
      hoverBorderColor: COLORS.gray300,
      activeBorderColor: COLORS.blue600,
      activeShadow: '0 0 0 3px rgba(27, 97, 201, 0.12)',
      colorIcon: COLORS.ink400,
      colorIconHover: COLORS.ink700,
      paddingInline: 10,
    },

    Select: {
      borderRadius: 6,
      borderRadiusLG: 6,
      borderRadiusSM: 4,
      controlHeight: 32,
      colorBgContainer: COLORS.white,
      colorBorder: COLORS.gray200,
      colorTextPlaceholder: COLORS.ink400,
      optionSelectedBg: COLORS.blue050,
      optionSelectedColor: COLORS.blue600,
      optionActiveBg: COLORS.gray050,
      multipleItemBg: COLORS.gray050,
      multipleItemBorderColor: COLORS.gray150,
    },

    Modal: {
      borderRadiusLG: 10,
      colorBgElevated: COLORS.white,
      colorBgMask: 'rgba(24, 29, 38, 0.45)',
      paddingContentHorizontal: 24,
      paddingMD: 20,
      titleFontSize: 16,
      titleLineHeight: 1.5,
      headerBg: COLORS.white,
      footerBg: COLORS.white,
    },

    Tooltip: {
      colorBgSpotlight: COLORS.ink900,
      colorTextLightSolid: COLORS.white,
      borderRadius: 4,
      paddingSM: 6,
      padding: 8,
    },

    Dropdown: {
      colorBgElevated: COLORS.white,
      borderRadiusLG: 6,
      controlItemBgHover: COLORS.gray050,
      controlItemBgActive: COLORS.blue050,
      paddingBlock: 4,
    },

    Tag: {
      borderRadiusSM: 4,
      defaultBg: COLORS.gray050,
      defaultColor: COLORS.ink700,
    },

    Badge: {
      borderRadius: 999,
      colorBgContainer: COLORS.red600,
      fontSize: 11,
    },

    Tabs: {
      colorBorderSecondary: COLORS.gray150,
      itemSelectedColor: COLORS.blue600,
      itemHoverColor: COLORS.ink900,
      itemActiveColor: COLORS.blue600,
      inkBarColor: COLORS.blue600,
      titleFontSize: 14,
      horizontalMargin: '0 0 16px 0',
    },

    Switch: {
      colorPrimary: COLORS.blue600,
      colorPrimaryHover: COLORS.blue700,
      handleBg: COLORS.white,
      colorTextQuaternary: COLORS.gray200,
      colorTextTertiary: COLORS.gray150,
    },

    Breadcrumb: {
      lastItemColor: COLORS.ink900,
      linkColor: COLORS.ink400,
      linkHoverColor: COLORS.blue600,
      separatorColor: COLORS.gray300,
      fontSize: 13,
    },

    Pagination: {
      colorBgContainer: 'transparent',
      colorPrimary: COLORS.blue600,
      colorPrimaryHover: COLORS.blue700,
      itemActiveBg: COLORS.blue050,
      itemBg: 'transparent',
      itemSize: 30,
      borderRadius: 4,
    },

    Spin: {
      colorPrimary: COLORS.blue600,
      dotSize: 24,
      dotSizeLG: 32,
      dotSizeSM: 18,
    },

    Empty: {
      colorTextDescription: COLORS.ink400,
      colorText: COLORS.ink700,
      colorFill: COLORS.gray200,
    },

    Alert: {
      borderRadiusLG: 6,
      colorInfoBg: COLORS.blue050,
      colorInfoBorder: COLORS.blue100,
      colorSuccessBg: COLORS.green050,
      colorSuccessBorder: COLORS.green050,
      colorWarningBg: COLORS.amber050,
      colorWarningBorder: COLORS.amber050,
      colorErrorBg: COLORS.red050,
      colorErrorBorder: COLORS.red050,
    },

    Notification: {
      borderRadiusLG: 10,
      colorBgElevated: COLORS.white,
      boxShadow: '0 8px 24px rgba(24, 29, 38, 0.14)',
    },

    Statistic: {
      contentFontSize: 28,
      titleFontSize: 13,
    },

    Descriptions: {
      labelBg: COLORS.gray025,
      titleColor: COLORS.ink900,
      contentColor: COLORS.ink700,
    },

    Divider: {
      colorSplit: COLORS.gray150,
    },
  },
};

export default theme;
