import { useMemo } from 'react';
import { Typography, Empty, Spin, Tooltip } from 'antd';
import {
  BarChartOutlined, TableOutlined, AppstoreOutlined,
  CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { dataApi } from '../api/data';
import type { FieldDefinition, RowData } from '../types/data';

const { Text } = Typography;

// 暗色图表主题色盘
const COLORS = ['#5e6ad2', '#02b8cc', '#27a644', '#f0a020', '#eb5757', '#8b5cf6', '#ec4899', '#f97316'];

interface StatCardProps {
  label: string;
  value: string | number;
  desc?: string;
  color?: string;
  icon?: React.ReactNode;
}

function StatCard({ label, value, desc, color = '#5e6ad2', icon }: StatCardProps) {
  return (
    <div className="stat-card" style={{ position: 'relative' }}>
      <div style={{
        position: 'absolute', top: 16, right: 20,
        width: 8, height: 8, borderRadius: 9999,
        background: color,
      }} />
      {icon && <div style={{ color, marginBottom: 4 }}>{icon}</div>}
      <span className="stat-card-label">{label}</span>
      <span className="stat-card-value" style={{ color }}>{value}</span>
      {desc && <span className="stat-card-desc">{desc}</span>}
    </div>
  );
}

function SimpleBar({ data, total }: { data: { label: string; value: number; color: string }[]; total: number }) {
  if (!data.length) return <Text style={{ color: '#62666d', fontSize: 13 }}>暂无数据</Text>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map((item) => {
        const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
        return (
          <div key={item.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text style={{ color: '#8a8f98', fontSize: 12 }}>{item.label}</Text>
              <Text style={{ color: '#d0d6e0', fontSize: 12, fontWeight: 510 }}>{item.value} <Text style={{ color: '#62666d', fontSize: 11 }}>({pct}%)</Text></Text>
            </div>
            <div style={{ height: 6, borderRadius: 9999, background: '#23252a', overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${pct}%`, borderRadius: 9999,
                background: item.color,
                transition: 'width 500ms cubic-bezier(0.25, 0.1, 0.25, 1)',
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
    queryKey: ['rows', 1, 99999], queryFn: () => dataApi.getRows({ page: 1, pageSize: 99999 }),
  });

  const allRows: RowData[] = rowsData?.data ?? [];
  const isLoading = columnsLoading || rowsLoading;

  // 列使用情况统计（每列非空值数量 / 总数）
  const columnUsage = useMemo(() => {
    if (!columns.length || !allRows.length) return [];
    return columns.map((col: FieldDefinition, idx: number) => {
      const filled = allRows.filter(r => r[col.key] !== null && r[col.key] !== undefined && r[col.key] !== '').length;
      return { label: col.label || col.key, key: col.key, filled, total: allRows.length, color: COLORS[idx % COLORS.length] };
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
        return { label: col.label || col.key, items: col.options.map((opt, i) => ({
          label: opt.label, value: dist.get(opt.value) || 0, color: COLORS[i % COLORS.length],
        })) };
      }
    }
    return null;
  }, [columns, allRows]);

  if (isLoading) return (
    <div style={{ padding: 80, textAlign: 'center' }}>
      <Spin size="large" />
    </div>
  );

  return (
    <div className="page-wrapper animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">数据总览</h1>
          <p className="page-subtitle">数据概况与完整性分析</p>
        </div>
      </div>

      {columns.length === 0 ? (
        <div className="card-surface" style={{ textAlign: 'center', padding: '60px 24px' }}>
          <Empty description={<span style={{ color: '#8a8f98' }}>暂无字段定义，请先在「数据列表」中添加字段</span>} />
        </div>
      ) : (
        <>
          {/* 顶部指标卡片 */}
          <div className="stats-grid">
            <StatCard
              label="总记录数" value={allRows.length}
              desc={`${allRows.length} 条数据`}
              color="#5e6ad2"
              icon={<TableOutlined />}
            />
            <StatCard
              label="字段数量" value={columns.length}
              desc={`${columns.length} 个字段`}
              color="#02b8cc"
              icon={<AppstoreOutlined />}
            />
            <StatCard
              label="数据完整度"
              value={allRows.length && columns.length
                ? `${Math.round(columnUsage.reduce((a, c) => a + c.filled, 0) / (columnUsage.length * allRows.length || 1) * 100)}%`
                : 'N/A'}
              desc="非空字段占比"
              color="#27a644"
              icon={<CheckCircleOutlined />}
            />
            <StatCard
              label="空值字段"
              value={allRows.length && columns.length
                ? columnUsage.reduce((a, c) => a + (c.total - c.filled), 0)
                : 0}
              desc="可优化项"
              color="#f0a020"
              icon={<ExclamationCircleOutlined />}
            />
          </div>

          {/* 下半部分两张卡 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* 列使用情况 */}
            <div className="card-surface">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <Text strong style={{ color: '#e5e5e6', fontSize: 16, letterSpacing: '-0.01em' }}>列填充率</Text>
                  <div><Text style={{ color: '#62666d', fontSize: 12 }}>各列非空值占比</Text></div>
                </div>
                <Tooltip title="非空值数量 / 总记录数">
                  <BarChartOutlined style={{ color: '#5e6ad2', fontSize: 18 }} />
                </Tooltip>
              </div>
              <SimpleBar
                data={columnUsage.slice(0, 8).map(c => ({
                  label: c.label, value: c.filled, color: c.color,
                }))}
                total={allRows.length}
              />
              {columnUsage.length > 8 && (
                <Text style={{ color: '#62666d', fontSize: 12, display: 'block', marginTop: 8 }}>
                  + 还有 {columnUsage.length - 8} 列未显示
                </Text>
              )}
            </div>

            {/* 分类分布 */}
            <div className="card-surface">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <Text strong style={{ color: '#e5e5e6', fontSize: 16, letterSpacing: '-0.01em' }}>分类分布</Text>
                  <div><Text style={{ color: '#62666d', fontSize: 12 }}>第一个下拉/布尔字段的选项分布</Text></div>
                </div>
                <AppstoreOutlined style={{ color: '#02b8cc', fontSize: 18 }} />
              </div>
              {topSelectColumn ? (
                <SimpleBar
                  data={topSelectColumn.items}
                  total={allRows.length}
                />
              ) : (
                <div style={{ padding: '20px 0', textAlign: 'center' }}>
                  <Text style={{ color: '#62666d', fontSize: 13 }}>暂无下拉/布尔类型字段</Text>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
