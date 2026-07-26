@echo off
chcp 65001 >nul

title 启动 Electron 桌面应用

echo.
echo ╔══════════════════════════════════════════════╗
echo ║  🖥️  动态数据登记系统 - Electron 桌面模式      ║
echo ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0electron"

:: 检查 Electron 是否安装
if not exist "node_modules\electron\package.json" (
    echo ❌ Electron 未安装！请先运行 install_electron.bat
    echo.
    pause
    cd /d "%~dp0"
    exit /b 1
)

:: 编译 TypeScript（如果 dist/main.js 不存在）
if not exist "dist\main.js" (
    echo [1/2] 编译 TypeScript...
    call node_modules\.bin\tsc.cmd -p tsconfig.json 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ⚠️  编译失败！请检查 src/main.ts 是否有语法错误。
        echo.
        echo 如果 src/main.ts 不存在，请确保 electron/src/ 目录完整。
        pause
        cd /d "%~dp0"
        exit /b 1
    )
    echo ✅ 编译完成
)

echo [2/2] 启动 Electron 窗口 ^(1400×900^)...
echo.
echo 窗口即将打开，关闭窗口时自动终止后端进程。
echo 如果窗口空白，请确保:
echo   1. Flask 后端运行在 127.0.0.1:5001
echo   2. Vite 前端运行在 localhost:5173
echo.
echo ═══════════════════════════════════════════════
echo.

:: 使用直接路径启动 Electron，避免依赖 npm/npx
call node_modules\.bin\electron.cmd dist/main.js

set EXIT_CODE=%ERRORLEVEL%

cd /d "%~dp0"

echo.
echo Electron 已退出（退出码: %EXIT_CODE%）
echo.
pause