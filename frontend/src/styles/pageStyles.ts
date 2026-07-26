/**
 * 页面级共享样式常量 — Linear-style Dark Theme
 * 供各页面组件引用，保持视觉一致性
 */
import React from 'react';
import type { CSSProperties } from 'react';

/* ── 页面容器 ── */
export const pageContainer: CSSProperties = {
  animation: 'fadeIn 0.3s ease-out both',
};

/* ── 页面标题区 ── */
export const pageHeaderStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 24,
  flexWrap: 'wrap',
  gap: 12,
};

export const pageTitleStyle: CSSProperties = {
  fontSize: 20,
  fontWeight: 500,
  color: 'var(--text-primary)',
  letterSpacing: '-0.5px',
  margin: 0,
};

/* ── 卡片容器 ── */
export const cardStyle: CSSProperties = {
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-xl)',
};

/* ── 搜索/筛选栏 ── */
export const searchBarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  marginBottom: 16,
  flexWrap: 'wrap',
};

/* ── 表格容器（带圆角边框） ── */
export const tableWrapperStyle: CSSProperties = {
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-xl)',
  overflow: 'hidden',
};

/* ── 统计卡片 ── */
export const statCardStyle: CSSProperties = {
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-xl)',
  padding: '20px 24px',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  transition: 'border-color 0.15s ease, background 0.15s ease',
};

export const statCardValueStyle: CSSProperties = {
  fontSize: 24,
  fontWeight: 600,
  color: 'var(--text-primary)',
  lineHeight: 1.25,
  letterSpacing: '-0.5px',
};

export const statCardLabelStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--text-secondary)',
};

/* ── 操作栏（表格上方） ── */
export const toolbarStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  flexWrap: 'wrap',
};

/* ── ECharts 图表暗色主题（仅 Stats / Charts 页面使用，此处不接入 token 体系） ── */
export const chartColors = ['#5e6ad2', '#0eb478', '#f5a623', '#e5484d', '#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899'];
export const chartTextColor = 'var(--text-secondary, #8a8f98)';
export const chartGridStyle = { borderColor: 'var(--surface-smoke, #262626)' };

export function getChartBaseOption(unit = ''): Record<string, unknown> {
  return {
    tooltip: {
      backgroundColor: 'var(--surface-obsidian, #1f1f1f)',
      borderColor: 'var(--surface-graphite, #262626)',
      textStyle: { color: 'var(--text-default, #ededed)', fontSize: 12 },
      extraCssText: 'border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);',
    },
    grid: { containLabel: true },
    textStyle: { color: chartTextColor, fontSize: 12 },
    ...(unit ? { tooltip: { valueFormatter: (v: unknown) => `${v} ${unit}` } } : {}),
  };
}

/* ── 审批状态标签色映射 ── */
export const statusTagMap: Record<string, { color: string; bg: string }> = {
  '待审核': { color: '#f5a623', bg: 'rgba(245,166,35,0.1)' },
  '已通过': { color: '#0eb478', bg: 'rgba(14,180,120,0.1)' },
  '已拒绝': { color: '#e5484d', bg: 'rgba(229,72,77,0.1)' },
  '待同步': { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  '已失败': { color: '#e5484d', bg: 'rgba(229,72,77,0.1)' },
};
