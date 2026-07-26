import { useState, useMemo } from 'react';
import { Typography, Select, Spin, Space, Radio } from 'antd';
import {
  BarChartOutlined, LineChartOutlined, PieChartOutlined,
  AreaChartOutlined, DotChartOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useQuery } from '@tanstack/react-query';
import { statsApi } from '../api/stats';

const { Text } = Typography;

type ChartType = 'bar' | 'line' | 'pie' | 'area' | 'scatter';

const CHART_OPTIONS: { value: ChartType; label: string; icon: React.ReactNode }[] = [
  { value: 'bar',     label: '柱状图', icon: <BarChartOutlined /> },
  { value: 'line',    label: '折线图', icon: <LineChartOutlined /> },
  { value: 'pie',     label: '饼状图', icon: <PieChartOutlined /> },
  { value: 'area',    label: '面积图', icon: <AreaChartOutlined /> },
  { value: 'scatter', label: '散点图', icon: <DotChartOutlined /> },
];

// ── 默认色板 ──
const DEFAULT_COLORS = [
  '#5e6ad2', '#02b8cc', '#27a644', '#f0a020', '#eb5757',
  '#8b5cf6', '#ec4899', '#f97316', '#06b6d4', '#a78bfa',
];

// ── HSL 工具 ──
function hexToHsl(hex: string): [number, number, number] {
  let r = 0, g = 0, b = 0;
  const h = hex.replace('#', '');
  if (h.length === 3) {
    r = parseInt(h[0] + h[0], 16) / 255;
    g = parseInt(h[1] + h[1], 16) / 255;
    b = parseInt(h[2] + h[2], 16) / 255;
  } else {
    r = parseInt(h.substring(0, 2), 16) / 255;
    g = parseInt(h.substring(2, 4), 16) / 255;
    b = parseInt(h.substring(4, 6), 16) / 255;
  }
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let hVal = 0, s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) hVal = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) hVal = ((b - r) / d + 2) / 6;
    else hVal = ((r - g) / d + 4) / 6;
  }
  return [Math.round(hVal * 360), Math.round(s * 100), Math.round(l * 100)];
}

function hslToHex(h: number, s: number, l: number): string {
  const sNorm = s / 100, lNorm = l / 100;
  const c = (1 - Math.abs(2 * lNorm - 1)) * sNorm;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = lNorm - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  const toHex = (v: number) => Math.round((v + m) * 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** 基于用户自定义 primaryColor 生成 10 色调色板 */
function generatePalette(baseHex: string): string[] {
  const [h, s, l] = hexToHsl(baseHex);
  const palette: string[] = [baseHex];
  const rotations = [30, 60, 120, 150, 180, 210, 240, 270, 300];
  for (const rot of rotations) {
    palette.push(hslToHex((h + rot) % 360, Math.min(s + 5, 100), Math.min(Math.max(l, 35), 65)));
  }
  return palette;
}

/** 读取用户自定义配色 */
function getChartColors(): string[] {
  try {
    const raw = localStorage.getItem('ui_colors');
    if (!raw) return [...DEFAULT_COLORS];
    const c = JSON.parse(raw) as Record<string, string>;
    if (!c.primaryColor) return [...DEFAULT_COLORS];
    return generatePalette(c.primaryColor);
  } catch {
    return [...DEFAULT_COLORS];
  }
}

export default function Charts() {
  const [selectedField, setSelectedField] = useState<string | undefined>();
  const [chartType, setChartType] = useState<ChartType>('bar');

  // 动态读取用户自定义配色（切换后回到此页面即可生效）
  const chartColors = useMemo(() => getChartColors(), []);
  const primaryColor = chartColors[0];
  const secondaryColor = chartColors[1];

  const { data: fields = [], isLoading: fieldsLoading } = useQuery({
    queryKey: ['statFields'],
    queryFn: statsApi.getStatFields,
  });

  const { data: fieldStats, isLoading: statsLoading, isError } = useQuery({
    queryKey: ['fieldStats', selectedField],
    queryFn: () => statsApi.getFieldStats(selectedField!),
    enabled: !!selectedField,
  });

  const chartOption = useMemo(() => {
    if (!fieldStats || !fieldStats.items.length) return null;

    const names  = fieldStats.items.map((i: { name: string }) => i.name);
    const values = fieldStats.items.map((i: { value: number }) => i.value);

    // ---------- 饼图 ----------
    if (chartType === 'pie') {
      return {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item' as const,
          backgroundColor: '#1a1b1e',
          borderColor: '#2a2b30',
          textStyle: { color: '#e5e5e6' },
          formatter: '{b}: {c} ({d}%)',
        },
        legend: {
          type: 'scroll' as const,
          orient: 'vertical' as const,
          right: '3%',
          top: 'center',
          textStyle: { color: '#8a8f98', fontSize: 12 },
        },
        toolbox: {
          feature: { saveAsImage: { title: '保存' } },
          iconStyle: { borderColor: '#8a8f98' },
        },
        series: [{
          type: 'pie',
          radius: ['42%', '72%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 4, borderColor: '#131316', borderWidth: 2 },
          label: { show: true, position: 'outside' as const, color: '#8a8f98', fontSize: 11 },
          emphasis: { label: { show: true, fontSize: 15, fontWeight: 'bold' as const } },
          data: fieldStats.items.map((item: { name: string; value: number }, i: number) => ({
            name: item.name,
            value: item.value,
            itemStyle: { color: chartColors[i % chartColors.length] },
          })),
        }],
      };
    }

    // ---------- 公共坐标轴 ----------
    const categoryAxis = {
      type: 'category' as const,
      data: names,
      axisLine: { lineStyle: { color: '#2a2b30' } },
      axisTick: { lineStyle: { color: '#2a2b30' } },
      axisLabel: {
        color: '#8a8f98', fontSize: 11,
        rotate: names.length > 10 ? 45 : 0,
        interval: 0, overflow: 'truncate' as const, width: 100,
      },
    };
    const valueAxis = {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#2a2b30' } },
      axisLabel: { color: '#8a8f98' },
      splitLine: { lineStyle: { color: '#1e1f23' } },
    };
    const baseGrid = {
      left: '3%', right: '4%',
      bottom: names.length > 10 ? '15%' : '3%', top: '10%',
      containLabel: true,
    };
    const baseTooltip = {
      trigger: 'axis' as const,
      backgroundColor: '#1a1b1e',
      borderColor: '#2a2b30',
      textStyle: { color: '#e5e5e6', fontSize: 13 },
    };
    const toolbox = {
      feature: { saveAsImage: { title: '保存' } },
      iconStyle: { borderColor: '#8a8f98' },
    };

    // ---------- 柱状图 ----------
    if (chartType === 'bar') {
      const [h, s, l] = hexToHsl(primaryColor);
      const topColor = hslToHex(h, s, Math.min(l + 8, 70));
      const bottomColor = hslToHex(h, Math.max(s - 5, 20), Math.max(l - 10, 25));
      const hoverColor = hslToHex(h, Math.min(s + 10, 100), Math.min(l + 12, 75));
      return {
        backgroundColor: 'transparent',
        tooltip: baseTooltip, grid: baseGrid, toolbox,
        xAxis: categoryAxis, yAxis: valueAxis,
        series: [{
          type: 'bar', data: values,
          itemStyle: {
            color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: topColor }, { offset: 1, color: bottomColor }] },
            borderRadius: [4, 4, 0, 0],
          },
          emphasis: { itemStyle: { color: hoverColor } },
          barMaxWidth: 48,
        }],
      };
    }

    // ---------- 折线图 ----------
    if (chartType === 'line') {
      return {
        backgroundColor: 'transparent',
        tooltip: baseTooltip, grid: baseGrid, toolbox,
        xAxis: categoryAxis, yAxis: valueAxis,
        series: [{
          type: 'line', data: values, smooth: true,
          symbol: 'circle', symbolSize: 6,
          lineStyle: { color: primaryColor, width: 2.5 },
          itemStyle: { color: primaryColor },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: hexToRgba(primaryColor, 0.12) },
              { offset: 1, color: hexToRgba(primaryColor, 0.01) },
            ] } },
        }],
      };
    }

    // ---------- 面积图 ----------
    if (chartType === 'area') {
      return {
        backgroundColor: 'transparent',
        tooltip: baseTooltip, grid: baseGrid, toolbox,
        xAxis: categoryAxis, yAxis: valueAxis,
        series: [{
          type: 'line', data: values, smooth: true,
          symbol: 'circle', symbolSize: 4,
          lineStyle: { color: secondaryColor, width: 2 },
          itemStyle: { color: secondaryColor },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: hexToRgba(secondaryColor, 0.35) },
              { offset: 1, color: hexToRgba(secondaryColor, 0.02) },
            ] } },
        }],
      };
    }

    // ---------- 散点图 ----------
    if (chartType === 'scatter') {
      return {
        backgroundColor: 'transparent',
        tooltip: { ...baseTooltip,
          formatter: (params: { value: number[] }) =>
            `值: ${params.value[0]}<br/>计数: ${params.value[1]}`,
        },
        grid: baseGrid, toolbox,
        xAxis: { ...valueAxis, name: fieldStats.field_label, nameTextStyle: { color: '#8a8f98' } },
        yAxis: valueAxis,
        series: [{
          type: 'scatter',
          data: fieldStats.items.map((item: { name: string; value: number }, i: number) => {
            const xVal = parseFloat(item.name);
            return isNaN(xVal) ? [i, item.value] : [xVal, item.value];
          }),
          symbolSize: (v: number[]) => Math.max(6, Math.min(32, v[1] * 1.5 + 4)),
          itemStyle: {
            color: { type: 'radial', x: 0.5, y: 0.5, r: 0.5,
              colorStops: [
                { offset: 0, color: primaryColor },
                { offset: 1, color: hexToRgba(primaryColor, 0.2) },
              ] },
          },
          emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 1 } },
        }],
      };
    }

    return null;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldStats, chartType, primaryColor, secondaryColor, chartColors]);

  // ======================== JSX ========================

  return (
    <div className="page-wrapper animate-fade-in">
      {/* 页面标题 */}
      <div className="page-header">
        <div>
          <h1 className="page-title">图表分析</h1>
          <p className="page-subtitle">选择字段与图表类型，灵活探索数据分布</p>
        </div>
        {fieldStats && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 22, fontWeight: 600, color: primaryColor, letterSpacing: '-0.02em' }}>
                {fieldStats.total}
              </div>
              <Text style={{ color: '#62666d', fontSize: 12 }}>记录总数</Text>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 22, fontWeight: 600, color: secondaryColor, letterSpacing: '-0.02em' }}>
                {fieldStats.items.length}
              </div>
              <Text style={{ color: '#62666d', fontSize: 12 }}>分类数</Text>
            </div>
          </div>
        )}
      </div>

      {/* 控制面板 */}
      <div className="card-surface" style={{ marginBottom: 16, padding: '16px 20px' }}>
        <Space size="large" wrap align="start">
          <div>
            <Text style={{ color: '#8a8f98', fontSize: 12, display: 'block', marginBottom: 6 }}>
              选择字段
            </Text>
            <Select
              placeholder="请选择要分析的字段"
              style={{ width: 260 }}
              loading={fieldsLoading}
              value={selectedField}
              onChange={setSelectedField}
              options={fields.map(f => ({ value: f.key, label: f.label }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>

          <div>
            <Text style={{ color: '#8a8f98', fontSize: 12, display: 'block', marginBottom: 6 }}>
              图表类型
            </Text>
            <Radio.Group
              value={chartType}
              onChange={e => setChartType(e.target.value)}
              buttonStyle="solid"
              size="middle"
            >
              {CHART_OPTIONS.map(opt => (
                <Radio.Button key={opt.value} value={opt.value}>
                  <Space size={5} style={{ fontSize: 13 }}>
                    {opt.icon}
                    <span>{opt.label}</span>
                  </Space>
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>
        </Space>
      </div>

      {/* 图表区域 */}
      <div className="card-surface" style={{ minHeight: 460, padding: 24 }}>
        {!selectedField ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 420, flexDirection: 'column',
          }}>
            <BarChartOutlined style={{ fontSize: 56, color: '#1e1f23', marginBottom: 16 }} />
            <Text style={{ color: '#8a8f98', fontSize: 14 }}>请先选择一个字段开始分析</Text>
          </div>
        ) : statsLoading ? (
          <div style={{ padding: 80, textAlign: 'center' }}>
            <Spin size="large" />
            <div style={{ marginTop: 12, color: '#62666d', fontSize: 13 }}>正在加载数据...</div>
          </div>
        ) : isError ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 420, flexDirection: 'column' }}>
            <Text style={{ color: '#eb5757', marginBottom: 8 }}>加载统计数据失败，请重试</Text>
          </div>
        ) : fieldStats && fieldStats.items.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 420, flexDirection: 'column' }}>
            <Text style={{ color: '#8a8f98' }}>该字段暂无有效数据</Text>
          </div>
        ) : chartOption ? (
          <>
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <Text strong style={{ color: '#e5e5e6', fontSize: 16, letterSpacing: '-0.01em' }}>
                {fieldStats?.field_label}
              </Text>
              <Text style={{ color: '#62666d', fontSize: 13 }}>
                共 {fieldStats?.total} 条记录 · {fieldStats?.items.length} 个类别
              </Text>
            </div>
            <ReactECharts
              option={chartOption}
              style={{ height: 400, width: '100%' }}
              notMerge
              lazyUpdate
            />
          </>
        ) : null}
      </div>
    </div>
  );
}
