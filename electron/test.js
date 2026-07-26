const { app, BrowserWindow } = require('electron');

let win;

app.whenReady().then(() => {
  win = new BrowserWindow({
    width: 800,
    height: 600,
    show: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });
  win.loadURL('https://www.baidu.com');
  console.log('窗口已创建');
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});