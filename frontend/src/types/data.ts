// ==================== 字段 & 数据行 ====================
export type FieldType = 'text' | 'number' | 'date' | 'select' | 'textarea' | 'boolean' | 'file';

export interface FieldDefinition {
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  options: { label: string; value: string }[] | null;
  width: number;
  editable: boolean;
  sortable: boolean;
  options_text?: string;
}

export interface RowData {
  id: number;
  [key: string]: unknown;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  pageSize: number;
  data: T[];
}

// ==================== 用户相关 ====================
export type UserRole = 'boss' | 'hr' | 'employee' | 'custom';

export interface User {
  id: number;
  username: string;
  role: UserRole;
  permissions: string[];
  audit_enabled: boolean;
  created_at: string;
}

export interface UserFormValues {
  username: string;
  password?: string;
  role: UserRole;
  permissions: string[];
  audit_enabled: boolean;
}

// ==================== 审核相关 ====================
export type AuditStatus = 'pending' | 'approved' | 'rejected';
export type AuditType = 'create' | 'update' | 'delete' | 'import'
  | 'insert' | 'delete_column' | 'add_column' | 'update_column' | 'update_column_config' | 'rename_column'
  | 'clear_columns' | 'clear_rows' | 'clear_logs'
  | 'add_user' | 'update_user' | 'delete_user'
  | 'reset_database' | 'restore_backup';

export interface AuditItem {
  id: number;
  row_id: number | null;
  column_name: string | null;
  old_value: string | null;
  new_value: string | null;
  change_type: string;
  requested_by: number | null;
  /** 后端返回中文状态值（"待审核"/"已通过"/"已驳回"），前端通过 normalizeStatus 映射为英文 key */
  status: string;
  reviewed_by: number | null;
  review_comment: string | null;
  reviewed_at: string | null;
  created_at: string;
  applicant: string | null;
  applicant_role: string | null;
  /** 前端归一化字段：change_type → type */
  type?: AuditType | string;
  /** 前端归一化字段：从 new_value 提取可读摘要 */
  detail?: string;
  /** 前端归一化字段：审核人用户名（后端未返回，预留） */
  reviewer?: string | null;
}

// ==================== 日志相关 ====================
export interface LogItem {
  id: number;
  timestamp: string;
  username: string;
  role: string;
  action: string;
  detail: string;
}

// ==================== 统计相关 ====================
export interface StatItem {
  name: string;
  value: number;
}

export interface FieldStats {
  field_key: string;
  field_label: string;
  total: number;
  items: StatItem[];
}

// ==================== 设置相关 ====================
export type DBEngine = 'sqlite' | 'mysql';

export interface AppSettings {
  db_engine: DBEngine;
  mysql_host: string;
  mysql_port: number;
  mysql_user: string;
  mysql_password: string;
  mysql_database: string;
}

// ==================== 备份相关 ====================
export interface BackupInfo {
  filename: string;
  size_bytes: number;
  created_at: string;
}