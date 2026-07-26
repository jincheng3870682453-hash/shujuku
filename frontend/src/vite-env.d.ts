/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// echarts 树摇模块类型声明
declare module 'echarts/lib/echarts' {
  import * as echarts from 'echarts';
  export = echarts;
}
declare module 'echarts/lib/chart/bar';
declare module 'echarts/lib/chart/pie';
declare module 'echarts/lib/chart/line';
declare module 'echarts/lib/component/tooltip';
declare module 'echarts/lib/component/title';
declare module 'echarts/lib/component/legend';
declare module 'echarts/lib/component/grid';
