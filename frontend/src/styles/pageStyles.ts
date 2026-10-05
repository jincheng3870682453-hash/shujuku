/**
 * 页面级共享样式常量
 * 选定方向：B · Airtable Grid View 标杆迁移
 *
 * ⚠️ 本文件的所有值必须引用 tokens.css 的 L2（语义层）/ L3（度量层），
 *    禁止出现硬编码色值——此前本文件与 tokens.css / textures.css /
 *    theme.ts / 页面行内样式构成四套并行体系，是本次重构要消除的核心问题。
 */
import type { CSSProperties } from 'react';

/* ── 页面容器 ── */
export const pageContainer: CSSProperties = {
  animation: 'fadeIn 0.18s cubic-bezier(0.4,0,0.2,1) both',
};

/* ── 页头 ── */
export const pageHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'flex-end',
  justifyContent: 'space-between',
  gap: 'var(--space-4)',
  marginBottom: 'var(--space-4)',
  flexWrap: 'wrap',
};

export const pageTitleStyle: CSSProperties = {
  fontSize: 'var(--fs-20)',
  fontWeight: 600,
  color: 'var(--ink-primary)',
  letterSpacing: '-0.01em',
  margin: 0,
};

export const pageSubtitleStyle: CSSProperties = {
  fontSize: 'var(--fs-12)',
  color: 'var(--ink-muted)',
  marginTop: 2,
};

/* ── 卡片 / 面板 ── */
export const cardStyle: CSSProperties = {
  background: 'var(--surface-base)',
  border: '1px solid var(--line-frame)',
  borderRadius: 'var(--radius-lg)',
};

export const panelInsetStyle: CSSProperties = {
  background: 'var(--surface-sunken)',
  border: '1px solid var(--line-soft)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--space-4)',
};

/* ── 表格容器（B 版：全幅贴边，无圆角卡片包裹）── */
export const tableWrapperStyle: CSSProperties = {
  border: '1px solid var(--line-frame)',
  borderRadius: 0,
  overflow: 'hidden',
};

/* ── 统计指标卡（统一实现，替代原先 4 套）── */
export const statCardStyle: CSSProperties = {
  background: 'var(--surface-base)',
  border: '1px solid var(--line-frame)',
  borderRadius: 'var(--radius-lg)',
  padding: 'var(--space-4)',
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  transition: 'border-color var(--t-fast)',
};

export const statCardValueStyle: CSSProperties = {
  fontSize: 'var(--fs-28)',
  fontWeight: 600,
  color: 'var(--ink-primary)',
  lineHeight: 1.2,
  letterSpacing: '-0.02em',
  fontVariantNumeric: 'tabular-nums',
};

export const statCardLabelStyle: CSSProperties = {
  fontSize: 'var(--fs-12)',
  color: 'var(--ink-muted)',
  fontWeight: 500,
};

/* ── 工具栏（登记条内的工具组）── */
export const toolbarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-2)',
  flexWrap: 'wrap',
};

/* ── ECharts 图表配置（跟随语义层，不再硬编码暗色）── */
export const chartColors = [
  '#1b61c9', '#2f8f52', '#c98a00', '#b42318',
  '#5c6470', '#17529f', '#14622f', '#7a4e00',
];

export function getChartBaseOption(unit = ''): Record<string, unknown> {
  return {
    tooltip: {
      backgroundColor: 'var(--surface-base)',
      borderColor: 'var(--line-frame)',
      borderWidth: 1,
      textStyle: { color: 'var(--ink-default)', fontSize: 12 },
      extraCssText: 'border-radius: 6px; box-shadow: 0 2px 8px rgba(24,29,38,0.10);',
      ...(unit ? { valueFormatter: (v: unknown) => `${v} ${unit}` } : {}),
    },
    grid: { containLabel: true },
    textStyle: { color: 'var(--ink-default)', fontSize: 12 },
  };
}

/* ── 状态 pill 映射（统一实现）
    彩色只服务「状态」这一个扫读维度，其余全部灰阶化 */
export type PillTone = 'on' | 'try' | 'off' | 'wait' | 'pass' | 'deny' | 'info';

export const statusPillClass: Record<PillTone, string> = {
  on: 'pill pill--on',
  try: 'pill pill--try',
  off: 'pill pill--off',
  wait: 'pill pill--wait',
  pass: 'pill pill--pass',
  deny: 'pill pill--deny',
  info: 'pill pill--info',
};

/** 中文状态 → pill 语义（审核流与在职状态共用一套） */
export const statusToneMap: Record<string, PillTone> = {
  // 在职状态
  在职: 'on',
  试用: 'try',
  离职: 'off',
  // 审核状态
  待审核: 'wait',
  已通过: 'pass',
  已驳回: 'deny',
  已拒绝: 'deny',
  // 通用
  启用: 'on',
  停用: 'off',
  正常: 'on',
  异常: 'deny',
  运行中: 'on',
  暂无数据: 'off',
};
