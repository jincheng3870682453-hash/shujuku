import { useMemo } from 'react';
import { Typography, Empty, Spin, Tooltip } from 'antd';
import { BarChartOutlined, AppstoreOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { dataApi } from '../api/data';
import type { FieldDefinition, RowData } from '../types/data';
import { chartColors } from '../styles/pageStyles';

const { Text } = Typography;

/** 统计取样条数：与后端 /api/stats 的 LIMIT 1000 口径一致，避免全量拉取 */
const SAMPLE_SIZE = 1000;

interface BarItem {
  label: string;
  value: number;
  color: string;
}

function SimpleBar({ data, total }: { data: BarItem[]; total: number }) {
  if (!data.length) return <Text type="secondary">暂无数据</Text>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {data.map((item) => {
        const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
        return (
          <div key={item.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
              <Text style={{ color: 'var(--ink-default)', fontSize: 'var(--fs-12)' }}>{item.label}</Text>
              <Text className="tnum" style={{ color: 'var(--ink-primary)', fontSize: 'var(--fs-12)', fontWeight: 500 }}>
                {item.value} <Text style={{ color: 'var(--ink-muted)', fontSize: 'var(--fs-11)' }}>({pct}%)</Text>
              </Text>
            </div>
            {/* 轨道用下沉面 + 细线，填充色取 chartColors（语义层派生） */}
            <div style={{
              height: 6,
              borderRadius: 'var(--radius-pill)',
              background: 'var(--surface-sunken)',
              border: '1px solid var(--line-soft)',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${pct}%`,
                borderRadius: 'var(--radius-pill)',
                background: item.color,
                transition: 'width 500ms var(--ease)',
                minWidth: pct > 0 ? 4 : 0,
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Stats() {
  const { data: columns = [], isLoading: columnsLoading } = useQuery({
    queryKey: ['columns'], queryFn: dataApi.getColumns, staleTime: 30 * 1000,
  });
  const { data: rowsData, isLoading: rowsLoading } = useQuery({
    queryKey: ['rows', 'stats-sample', SAMPLE_SIZE],
    queryFn: () => dataApi.getRows({ page: 1, pageSize: SAMPLE_SIZE }),
  });

  const allRows: RowData[] = rowsData?.data ?? [];
  /** 全库真实总数（用于「总记录数」指标）；其余指标基于取样数据计算 */
  const totalRows = rowsData?.total ?? allRows.length;
  const isLoading = columnsLoading || rowsLoading;

  // 列使用情况统计（每列非空值数量 / 取样总数）
  const columnUsage = useMemo(() => {
    if (!columns.length || !allRows.length) return [];
    return columns.map((col: FieldDefinition, idx: number) => {
      const filled = allRows.filter(r => r[col.key] !== null && r[col.key] !== undefined && r[col.key] !== '').length;
      return {
        label: col.label || col.key,
        key: col.key,
        filled,
        total: allRows.length,
        color: chartColors[idx % chartColors.length],
      };
    }).sort((a, b) => b.filled - a.filled);
  }, [columns, allRows]);

  // 按列的 select/boolean 选项分布
  const topSelectColumn = useMemo(() => {
    for (const col of columns as FieldDefinition[]) {
      if ((col.type === 'select' || col.type === 'boolean') && Array.isArray(col.options) && col.options.length) {
        const dist = new Map<string, number>();
        allRows.forEach(r => {
          const v = r[col.key];
          if (v !== null && v !== undefined) dist.set(String(v), (dist.get(String(v)) || 0) + 1);
        });
        return {
          label: col.label || col.key,
          items: col.options.map((opt, i) => ({
            label: opt.label,
            value: dist.get(opt.value) || 0,
            color: chartColors[i % chartColors.length],
          })),
        };
      }
    }
    return null;
  }, [columns, allRows]);

  const completeness = allRows.length && columns.length
    ? `${Math.round(columnUsage.reduce((a, c) => a + c.filled, 0) / (columnUsage.length * allRows.length || 1) * 100)}%`
    : 'N/A';
  const emptyCells = allRows.length && columns.length
    ? columnUsage.reduce((a, c) => a + (c.total - c.filled), 0)
    : 0;

  if (isLoading) return (
    <div style={{ padding: 'var(--space-12) 0', textAlign: 'center' }}>
      <Spin size="large" />
    </div>
  );

  return (
    <div className="page-wrapper animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">数据总览</h1>
          <p className="page-subtitle">数据概况与完整性分析 · 基于最近 {SAMPLE_SIZE} 条取样</p>
        </div>
      </div>

      {columns.length === 0 ? (
        <div className="card-surface" style={{ textAlign: 'center', padding: 'var(--space-12) var(--space-6)' }}>
          <Empty description="暂无字段定义，请先在「数据列表」中添加字段" />
        </div>
      ) : (
        <>
          {/* 顶部指标卡片 —— 统一使用 index.css 的 .stat-card */}
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-card-label">总记录数</span>
              <span className="stat-card-value tnum">{totalRows}</span>
              <span className="stat-card-desc">{totalRows} 条数据</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-label">字段数量</span>
              <span className="stat-card-value tnum">{columns.length}</span>
              <span className="stat-card-desc">{columns.length} 个字段</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-label">数据完整度</span>
              <span className="stat-card-value tnum">{completeness}</span>
              <span className="stat-card-desc">非空字段占比</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-label">空值字段</span>
              <span className="stat-card-value tnum">{emptyCells}</span>
              <span className="stat-card-desc">可优化项</span>
            </div>
          </div>

          {/* 下半部分两张卡 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
            {/* 列使用情况 */}
            <div className="card-surface">
              <div style={{
                display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                gap: 'var(--space-3)', marginBottom: 'var(--space-4)',
              }}>
                <div>
                  <div style={{ fontSize: 'var(--fs-14)', fontWeight: 600, color: 'var(--ink-primary)' }}>列填充率</div>
                  <p className="page-subtitle">各列非空值占比</p>
                </div>
                <Tooltip title="非空值数量 / 取样记录数">
                  <BarChartOutlined style={{ color: 'var(--ink-muted)', fontSize: 16 }} />
                </Tooltip>
              </div>
              <SimpleBar
                data={columnUsage.slice(0, 8).map(c => ({
                  label: c.label, value: c.filled, color: c.color,
                }))}
                total={allRows.length}
              />
              {columnUsage.length > 8 && (
                <p className="page-subtitle" style={{ marginTop: 'var(--space-3)' }}>
                  + 还有 {columnUsage.length - 8} 列未显示
                </p>
              )}
            </div>

            {/* 分类分布 */}
            <div className="card-surface">
              <div style={{
                display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                gap: 'var(--space-3)', marginBottom: 'var(--space-4)',
              }}>
                <div>
                  <div style={{ fontSize: 'var(--fs-14)', fontWeight: 600, color: 'var(--ink-primary)' }}>分类分布</div>
                  <p className="page-subtitle">第一个下拉/布尔字段的选项分布</p>
                </div>
                <AppstoreOutlined style={{ color: 'var(--ink-muted)', fontSize: 16 }} />
              </div>
              {topSelectColumn ? (
                <SimpleBar
                  data={topSelectColumn.items}
                  total={allRows.length}
                />
              ) : (
                <div style={{ padding: 'var(--space-5) 0', textAlign: 'center' }}>
                  <Text type="secondary">暂无下拉/布尔类型字段</Text>
                </div>
              )}
            </div>
          </div>

          {/* 取样口径说明 */}
          <div className="thin-note" style={{ marginTop: 'var(--space-4)', border: '1px solid var(--line-soft)', borderRadius: 'var(--radius-md)' }}>
            完整性指标基于最近 {SAMPLE_SIZE} 条记录取样统计，与后端统计接口口径一致
          </div>
        </>
      )}
    </div>
  );
}
