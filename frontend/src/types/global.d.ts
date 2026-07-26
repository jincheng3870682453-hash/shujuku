export {};

declare global {
  interface Window {
    electronAPI: {
      saveFile: (options: {
        defaultPath: string;
        filters: Array<{ name: string; extensions: string[] }>;
        data: string;
      }) => Promise<{
        success: boolean;
        path?: string;
        canceled?: boolean;
        error?: string;
      }>;
    };
  }
}