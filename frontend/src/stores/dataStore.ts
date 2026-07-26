import { create } from 'zustand';
import type { RowData } from '../types/data';

interface DataStore {
  rows: RowData[];
  total: number;
  page: number;
  pageSize: number;
  keyword: string;
  loading: boolean;
  selectedRowKeys: React.Key[];

  setRows: (rows: RowData[]) => void;
  setTotal: (total: number) => void;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setKeyword: (keyword: string) => void;
  setLoading: (loading: boolean) => void;
  setSelectedRowKeys: (keys: React.Key[]) => void;
  reset: () => void;
}

const initialState = {
  rows: [] as RowData[],
  total: 0,
  page: 1,
  pageSize: 20,
  keyword: '',
  loading: false,
  selectedRowKeys: [] as React.Key[],
};

export const useDataStore = create<DataStore>((set) => ({
  ...initialState,

  setRows: (rows) => set({ rows }),
  setTotal: (total) => set({ total }),
  setPage: (page) => set({ page }),
  setPageSize: (pageSize) => set({ pageSize, page: 1 }),
  setKeyword: (keyword) => set({ keyword, page: 1 }),
  setLoading: (loading) => set({ loading }),
  setSelectedRowKeys: (selectedRowKeys) => set({ selectedRowKeys }),
  reset: () => set(initialState),
}));