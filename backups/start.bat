@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title 动态数据登记系统 - 启动脚本

echo =========================================
echo   动态数据登记系统 - Windows 启动脚本
echo =========================================
echo.
echo 请选择启动模式：
echo   1) Web 版（Flask 后端 + 内嵌页面）
echo   2) 前后端分离开发（Flask + Vite dev server）
echo   3) Electron 桌面版
echo.
set /p MODE="请输入选项 [1/2/3] (默认 1): "
if "%MODE%"=="" set MODE=1

REM ==========================================
REM 第一步：检查 Python 环境
REM ==========================================
echo.
echo [检查] Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo        检测到 Python %PYVER%

for /f "tokens=1 delims=." %%a in ("%PYVER%") do set PYMAJOR=%%a
if %PYMAJOR% LSS 3 (
    echo [错误] Python 版本过低，需要 3.10+
    pause
    exit /b 1
)

REM ==========================================
REM 第二步：安装 Python 依赖
REM ==========================================
echo.
echo [安装] Python 依赖...
cd /d "%~dp0"
python -m pip install -r requirements.txt --quiet 2>nul
if %errorlevel% neq 0 (
    echo        尝试使用清华镜像...
    python -m pip install -r requirements.txt --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
)
python -m pip install -r backend/requirements.txt --quiet 2>nul
if %errorlevel% neq 0 (
    python -m pip install -r backend/requirements.txt --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
)
echo        依赖检查完成

REM ==========================================
REM 第三步：创建 backend/.env（如果不存在）
REM ==========================================
if not exist "%~dp0backend\.env" (
    echo DB_ENGINE=sqlite > "%~dp0backend\.env"
    echo SQLITE_PATH=.\data\app.db >> "%~dp0backend\.env"
)

REM ==========================================
REM 第四步：检查 Node.js（仅模式 2/3 需要）
REM ==========================================
if "%MODE%"=="2" goto check_node
if "%MODE%"=="3" goto check_node
goto skip_node_check

:check_node
echo.
echo [检查] Node.js 环境...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Node.js，模式 %MODE% 需要 Node.js 20+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo        Node.js %%i
goto skip_node_check

:skip_node_check

REM ==========================================
REM 第五步：按模式启动
REM ==========================================
echo.
echo =========================================
if "%MODE%"=="1" goto start_web
if "%MODE%"=="2" goto start_dev
if "%MODE%"=="3" goto start_electron

:start_web
echo   启动模式：Web 版
echo   后端地址: http://localhost:5001
echo   按 Ctrl+C 停止服务
echo =========================================
echo.
cd /d "%~dp0"
python app.py
goto end

:start_dev
echo   启动模式：前后端分离开发
echo   后端地址: http://localhost:5001
echo   前端地址: http://localhost:3000
echo   按 Ctrl+C 停止全部服务
echo =========================================
echo.

REM 检查前端依赖
if not exist "%~dp0frontend\node_modules" (
    echo [安装] 前端依赖...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

REM 启动后端（新窗口）
echo [启动] 后端服务...
start "Flask Backend" cmd /c "cd /d %~dp0 && python app.py"

REM 等待后端就绪
echo [等待] 后端启动中（5秒）...
timeout /t 5 /nobreak >nul

REM 启动前端
echo [启动] 前端 Vite dev server...
cd /d "%~dp0frontend"
call npx vite --host
goto end

:start_electron
echo   启动模式：Electron 桌面版
echo   后端将由 Electron 自动管理
echo =========================================
echo.

REM 检查 Electron 依赖
if not exist "%~dp0electron\node_modules" (
    echo [安装] Electron 依赖...
    cd /d "%~dp0electron"
    call npm install
    cd /d "%~dp0"
)

REM 编译 TypeScript（如果 dist 不存在）
if not exist "%~dp0electron\dist\main.js" (
    echo [编译] Electron TypeScript...
    cd /d "%~dp0electron"
    call npx tsc -p tsconfig.json
    if %errorlevel% neq 0 (
        echo [错误] TypeScript 编译失败
        cd /d "%~dp0"
        pause
        exit /b 1
    )
    cd /d "%~dp0"
    echo        编译完成
)

echo [启动] Electron 桌面应用...
cd /d "%~dp0electron"
call npx electron dist/main.js
goto end

:end
echo.
echo 应用已退出。
pause
endlocal