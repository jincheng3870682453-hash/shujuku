@echo off
chcp 65001 >nul
title 灵登记 · 数据登记系统

:menu
cls
echo.
echo  ╔════════════════════════════════╗
echo  ║     📋 灵登记 · 数据登记系统   ║
echo  ╚════════════════════════════════╝
echo.
echo  预设账号：
echo    Boss     - boss     / 123456
echo    HR       - hr       / 123456
echo    Employee - employee / 123456
echo.
echo  ──────────────────────────────────
echo    [1] Web 模式    (浏览器访问)
echo    [2] 桌面模式    (pywebview)
echo    [0] 退出
echo  ──────────────────────────────────
echo.
set /p choice="  请选择启动方式: "

if "%choice%"=="1" goto web
if "%choice%"=="2" goto desktop
if "%choice%"=="0" exit /b
goto menu

:web
cls
echo ================================
echo    📋 灵登记 · Web 模式启动中...
echo ================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python 环境！
    echo 请先安装 Python 3.8 或更高版本
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b
)

:: 显示 Python 版本
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo ✅ 检测到 %PYTHON_VER%
echo.

:: 检查依赖是否已安装
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo 📦 检测到缺少依赖，正在自动安装...
    echo.
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请检查网络连接后重试
        pause
        exit /b
    )
    echo ✅ 依赖安装完成
    echo.
) else (
    echo ✅ 依赖检查通过
    echo.
)

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 启动应用
echo 🚀 正在启动服务...
echo.
echo ================================
echo   服务地址: http://127.0.0.1:5001
echo   按 Ctrl+C 可停止服务
echo ================================
echo.

python run.py

:: 如果程序异常退出，暂停让用户看到错误
echo.
echo ❌ 服务已停止（按任意键退出）
pause
goto menu

:desktop
cls
echo ================================
echo    📋 灵登记 · 桌面模式启动中...
echo ================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python 环境！
    pause
    exit /b
)

:: 检查 pywebview 依赖
python -c "import pywebview" >nul 2>&1
if errorlevel 1 (
    echo 📦 桌面模式需要 pywebview，正在安装...
    echo.
    pip install pywebview -q
    if errorlevel 1 (
        echo ❌ pywebview 安装失败
        echo 请手动执行: pip install pywebview
        pause
        goto menu
    )
    echo ✅ pywebview 安装完成
    echo.
)

:: 检查其他依赖
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    pip install -r requirements.txt -q
    echo ✅ 依赖安装完成
    echo.
)

:: 切换到脚本所在目录
cd /d "%~dp0"

echo 🚀 正在启动桌面应用...
echo.

python desktop.py

echo.
echo ❌ 桌面应用已关闭（按任意键返回菜单）
pause
goto menu