import { create } from 'zustand';
import type { FieldDefinition } from '../types/data';

interface ColumnStore {
  columns: FieldDefinition[];
  loaded: boolean;
  setColumns: (cols: FieldDefinition[]) => void;
  markLoaded: () => void;
  reset: () => void;
}

export const useColumnStore = create<ColumnStore>((set) => ({
  columns: [],
  loaded: false,
  setColumns: (columns) => set({ columns, loaded: true }),
  markLoaded: () => set({ loaded: true }),
  reset: () => set({ columns: [], loaded: false }),
}));