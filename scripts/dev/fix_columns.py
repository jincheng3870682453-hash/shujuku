# -*- coding: utf-8 -*-
"""
动态数据登记系统 - 自动补齐 rows_data 缺失列
从 columns_meta 读取所有字段名，检查 rows_data 中是否缺少对应列，如缺失则自动添加。
保留现有数据，只添加列，不删除任何列。
"""

import sys
from backend.db_adapter import get_adapter

# 字段类型到 SQL 类型的映射
TYPE_MAP = {
    'text': 'VARCHAR(255)',
    'number': 'DOUBLE',
    'date': 'VARCHAR(255)',
    'select': 'VARCHAR(255)',
    'boolean': 'INT',
    'textarea': 'TEXT',
    'file': 'TEXT',
}


def main():
    db = get_adapter()
    try:
        # 1. 读取 columns_meta 中所有字段定义
        cols = db.fetch_all(
            "SELECT name, field_type, label FROM columns_meta ORDER BY position ASC"
        )
        if not cols:
            print("columns_meta 表为空，无需同步。")
            return

        print(f"=== columns_meta 中共 {len(cols)} 个字段 ===")
        for c in cols:
            print(f"  {c['name']}  ({c['field_type']})  — {c.get('label', '')}")

        # 2. 获取 rows_data 现有列名
        existing = set()
        try:
            rows = db.fetch_all("SHOW COLUMNS FROM rows_data")
            # 不同驱动返回格式不同：MySQL tuple / 字典
            for row in rows:
                if isinstance(row, dict):
                    existing.add(row.get('Field', ''))
                elif isinstance(row, (tuple, list)):
                    existing.add(row[0] if len(row) > 0 else '')
        except Exception as e:
            print(f"警告: 获取 rows_data 列信息失败: {e}")
            return

        print(f"\n=== rows_data 现有列 ({len(existing)}) ===")
        for col_name in sorted(existing):
            print(f"  {col_name}")

        # 3. 找出缺失的列并添加
        missing = [c for c in cols if c['name'] not in existing]

        if not missing:
            print("\n✅ 所有列已同步，无需修复。")
            return

        print(f"\n=== 缺失 {len(missing)} 列，开始自动补齐 ===")
        added = []
        failed = []
        for c in missing:
            col_name = c['name']
            field_type = c.get('field_type', 'text')
            sql_type = TYPE_MAP.get(field_type, 'VARCHAR(255)')
            sql = f"ALTER TABLE rows_data ADD COLUMN {col_name} {sql_type}"
            try:
                db.execute_query(sql)
                added.append(col_name)
                print(f"  ✅ 已添加列: {col_name} ({sql_type})")
            except Exception as e:
                failed.append((col_name, str(e)))
                print(f"  ❌ 添加列 {col_name} 失败: {e}")

        # 4. 汇总
        print(f"\n=== 修复汇总 ===")
        print(f"  columns_meta 字段数: {len(cols)}")
        print(f"  rows_data 原有列数: {len(existing)}")
        print(f"  成功添加: {len(added)} 列")
        if added:
            for name in added:
                print(f"    + {name}")
        if failed:
            print(f"  添加失败: {len(failed)} 列")
            for name, err in failed:
                print(f"    ✗ {name}: {err}")
        print(f"  rows_data 现有列数: {len(existing) + len(added)}")
        print("✅ 修复完成！")
    finally:
        db.close()


if __name__ == '__main__':
    main()