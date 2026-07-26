@echo off
chcp 65001 >nul

title 安装 Electron 依赖

echo.
echo ╔══════════════════════════════════════════════╗
echo ║  📦 安装 Electron 依赖                        ║
echo ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0electron"

:: 检查 node_modules 是否完整
if exist "node_modules\electron\package.json" (
    echo ✅ Electron 已安装:
    node -e "console.log(require('electron/package.json').version)" 2>nul
    echo.
    echo 如需重新安装，请先删除 node_modules 文件夹。
    pause
    cd /d "%~dp0"
    exit /b 0
)

echo 正在清理旧的依赖缓存...
if exist "node_modules" rmdir /s /q "node_modules" 2>nul
if exist "package-lock.json" del "package-lock.json" 2>nul

echo.
echo 正在安装 Electron（首次约需下载 100MB，请耐心等待）...
echo.
call npm install

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 安装失败！可能的原因：
    echo    1. 网络问题 - 请检查网络连接
    echo    2. npm 缓存损坏 - 请运行 npm cache clean --force
    echo    3. 磁盘空间不足
    echo.
    echo 手动安装命令：
    echo    cd electron
    echo    npm install
    pause
    cd /d "%~dp0"
    exit /b 1
)

echo.
echo ✅ Electron 安装完成！
echo.
node -e "console.log('版本:', require('electron/package.json').version)" 2>nul

cd /d "%~dp0"
pause