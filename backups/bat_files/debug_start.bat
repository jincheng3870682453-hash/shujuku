@echo off
chcp 65001 >nul

title 动态数据登记系统 - 调试模式

:: ============================================================
::  调试模式启动脚本
::  所有步骤在当前窗口执行，不使用 start 命令
::  每一步都暂停，让你看到输出
:: ============================================================

:step_1
cls
echo.
echo ╔══════════════════════════════════════════════╗
echo ║  🔍 动态数据登记系统 - 调试模式              ║
echo ║  所有步骤在当前窗口执行，不会闪退            ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 如果任何步骤报错，错误信息会直接显示。
echo 按 Ctrl+C 可随时停止。
echo.
pause

:step_2
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 1/6：检查 Python 版本
echo ═══════════════════════════════════════════════
echo.
echo 执行命令: python --version
echo ───────────────────────────────────────────────
echo.
python --version
echo.
echo ───────────────────────────────────────────────
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python 未安装或不在 PATH 中！
    echo 下载: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo ✅ Python 可用（如果上面显示了版本号）
echo.
pause

:step_3
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 2/6：检查 Node.js 版本
echo ═══════════════════════════════════════════════
echo.
echo 执行命令: node --version
echo ───────────────────────────────────────────────
echo.
node --version
echo.
echo ───────────────────────────────────────────────
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js 未安装或不在 PATH 中！
    echo 下载: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo ✅ Node.js 可用（如果上面显示了版本号）
echo.
pause

:step_4
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 3/6：检查关键依赖
echo ═══════════════════════════════════════════════
echo.
echo 检查 Flask...
python -c "import flask; print('Flask', flask.__version__)" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Flask 未安装！正在安装...
    echo.
    pip install flask
    python -c "import flask" 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Flask 安装失败！请手动执行: pip install flask
        pause
        exit /b 1
    )
    echo ✅ Flask 安装完成
) else (
    echo ✅ Flask 可用
)

echo.
echo 检查 flask-cors...
python -c "import flask_cors" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ flask-cors 未安装！正在安装...
    pip install flask-cors
    python -c "import flask_cors" 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ flask-cors 安装失败！请手动执行: pip install flask-cors
        pause
        exit /b 1
    )
    echo ✅ flask-cors 安装完成
) else (
    echo ✅ flask-cors 可用
)

echo.
echo 检查前端目录...
if not exist "frontend\package.json" (
    echo ❌ frontend\package.json 不存在！
    pause
    exit /b 1
)
echo ✅ frontend\package.json 存在

if not exist "frontend\node_modules" (
    echo.
    echo ⚠️  node_modules 不存在，正在安装前端依赖...
    echo 这可能需要 1-2 分钟...
    cd frontend
    call npm install
    cd ..
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ npm install 失败！请手动执行: cd frontend ^&^& npm install
        pause
        exit /b 1
    )
    echo ✅ 前端依赖安装完成
) else (
    echo ✅ node_modules 已存在
)
echo.
pause

:step_5
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 4/6：启动 Flask 后端（前台运行）
echo ═══════════════════════════════════════════════
echo.
echo 正在启动 Flask 后端...
echo 后端将在此窗口运行，日志会直接显示在下方。
echo.
echo 正常情况下你会看到类似:
echo   "Running on http://127.0.0.1:5001"
echo.
echo 如果报错，错误信息会直接显示，窗口不会关闭。
echo 按 Ctrl+C 可停止 Flask，继续下一步。
echo.
echo ===============================================
echo.
cd /d "%~dp0"
python app.py

echo.
echo ===============================================
echo Flask 进程已停止（退出码: %ERRORLEVEL%）
echo.
echo 如果上面显示了 ImportError 或 ModuleNotFoundError:
echo   → 依赖缺失，请先运行 pip install -r requirements.txt
echo.
echo 如果显示了 "Address already in use":
echo   → 端口 5001 被占用，运行: netstat -ano ^| findstr ":5001"
echo.
pause

:step_6
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 5/6：手动测试 Flask 是否可访问
echo ═══════════════════════════════════════════════
echo.
echo 如果 Flask 仍在运行，请在浏览器中访问:
echo   http://127.0.0.1:5001/api/health
echo.
echo 正确响应应该是:
echo   {"message":"后端服务运行正常","status":"ok"}
echo.
echo 如果看到这个响应，说明 Flask 运行正常。
echo.
echo ⚠️  如果 Flask 已在上一步停止，请先修复错误再继续
echo.
pause

:step_7
cls
echo.
echo ═══════════════════════════════════════════════
echo  步骤 6/6：启动前端 Vite 开发服务器（前台运行）
echo ═══════════════════════════════════════════════
echo.
echo 正在启动前端开发服务器...
echo 前端将在此窗口运行，日志会直接显示在下方。
echo.
echo 正常运行后会看到类似:
echo   "Local:   http://localhost:5173/"
echo.
echo 请确保 Flask 后端已在另一个窗口运行中！
echo 如果没有，请先打开新的命令窗口运行: python app.py
echo.
echo 按 Ctrl+C 可停止前端。
echo.
echo ===============================================
echo.
cd /d "%~dp0frontend"
call npm run dev

echo.
echo ===============================================
echo 前端已停止。
echo.
pause

:step_end
cls
echo.
echo ╔══════════════════════════════════════════════╗
echo ║  🔍 调试完成                                  ║
echo ║                                              ║
echo ║  正常流程:                                    ║
echo ║  1. 新开一个窗口运行 python app.py            ║
echo ║  2. 当前窗口运行 npm run dev (在 frontend\)   ║
echo ║  3. 浏览器访问 http://localhost:5173         ║
echo ║                                              ║
echo ║  或者使用 启动.bat 选择 Web 模式自动启动      ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
exit /b 0