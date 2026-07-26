@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set LOG_FILE=startup.log
echo [%date% %time%] === 调试启动脚本开始 === > "%LOG_FILE%"

:: ========== 颜色定义 ==========
:: [OK] 绿色  [ERROR] 红色  [INFO] 白色  [STEP] 青色

:step_check_python
echo.
echo [STEP 1/8] 检查 Python 环境...
echo [%date% %time%] 检查 Python... >> "%LOG_FILE%"
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] Python 未安装或不在 PATH 中！[0m
    echo [ERROR] Python 未安装 >> "%LOG_FILE%"
    echo 请安装 Python 3.10+ https://www.python.org/downloads/
    goto error_exit
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [92m[OK] %PYVER%[0m
echo [OK] %PYVER% >> "%LOG_FILE%"
pause

:step_check_pip
echo.
echo [STEP 2/8] 检查 pip 是否可用...
echo [%date% %time%] 检查 pip... >> "%LOG_FILE%"
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] pip 不可用！请运行: python -m ensurepip --upgrade[0m
    echo [ERROR] pip 不可用 >> "%LOG_FILE%"
    goto error_exit
)
for /f "tokens=*" %%i in ('python -m pip --version 2^>^&1') do set PIPVER=%%i
echo [92m[OK] %PIPVER%[0m
echo [OK] %PIPVER% >> "%LOG_FILE%"
pause

:step_check_flask
echo.
echo [STEP 3/8] 检查 Flask 依赖是否安装...
echo [%date% %time%] 检查 Flask 依赖... >> "%LOG_FILE%"
python -c "import flask; print('Flask', flask.__version__)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [93m[WARN] Flask 未安装，正在安装依赖...[0m
    echo [WARN] 安装依赖 >> "%LOG_FILE%"
    python -m pip install -r requirements.txt 2>&1 >> "%LOG_FILE%"
    if %ERRORLEVEL% NEQ 0 (
        echo [91m[ERROR] 依赖安装失败！请手动执行: pip install -r requirements.txt[0m
        echo [ERROR] 依赖安装失败 >> "%LOG_FILE%"
        goto error_exit
    )
    echo [92m[OK] 依赖安装完成[0m
    echo [OK] 依赖安装完成 >> "%LOG_FILE%"
) else (
    for /f "tokens=*" %%i in ('python -c "import flask; print(flask.__version__)" 2^>^&1') do set FLASKVER=%%i
    echo [92m[OK] Flask !FLASKVER! 已安装[0m
    echo [OK] Flask !FLASKVER! >> "%LOG_FILE%"
)
pause

:step_check_flask_cors
echo [%date% %time%] 检查 flask-cors... >> "%LOG_FILE%"
python -c "import flask_cors" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [93m[WARN] flask-cors 未安装，正在安装...[0m
    echo [WARN] 安装 flask-cors >> "%LOG_FILE%"
    python -m pip install flask-cors 2>&1 >> "%LOG_FILE%"
    if %ERRORLEVEL% NEQ 0 (
        echo [91m[ERROR] flask-cors 安装失败！请手动执行: pip install flask-cors[0m
        echo [ERROR] flask-cors 安装失败 >> "%LOG_FILE%"
        goto error_exit
    )
    echo [92m[OK] flask-cors 安装完成[0m
) else (
    echo [92m[OK] flask-cors 已安装[0m
)

:step_start_backend
echo.
echo [STEP 4/8] 启动 Flask 后端...
echo [%date% %time%] 启动 Flask 后端... >> "%LOG_FILE%"

:: 端口检测
netstat -ano | findstr ":5001 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [91m[ERROR] 端口 5001 已被占用！请先关闭占用进程。[0m
    echo [ERROR] 端口 5001 已被占用 >> "%LOG_FILE%"
    echo 查看占用进程: netstat -ano ^| findstr ":5001"
    goto error_exit
)

start "Flask Backend" cmd /c "python app.py 2>&1 >> flask_output.log"
echo [INFO] Flask 已在新窗口启动，等待就绪...
echo [INFO] Flask 已在新窗口启动 >> "%LOG_FILE%"

:: 等待 /api/health 返回 200
set /a count=0
:wait_backend_debug
timeout /t 1 /nobreak >nul
set /a count+=1

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5001/api/health' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [92m[OK] 后端已就绪 ^(!count! 秒^)[0m
    echo [OK] 后端已就绪 ^(!count! 秒^) >> "%LOG_FILE%"
    goto step_check_node
)

if %count% GEQ 30 (
    echo [91m[ERROR] 后端 30 秒内未就绪！[0m
    echo [ERROR] 后端超时 >> "%LOG_FILE%"
    echo 请检查 flask_output.log 文件查看错误信息
    goto error_exit
)
goto wait_backend_debug

:step_check_node
echo.
echo [STEP 5/8] 检查 Node.js 环境...
echo [%date% %time%] 检查 Node.js... >> "%LOG_FILE%"
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] Node.js 未安装！[0m
    echo [ERROR] Node.js 未安装 >> "%LOG_FILE%"
    echo 下载地址: https://nodejs.org/
    goto error_exit
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODEVER=%%i
echo [92m[OK] Node.js %NODEVER%[0m
echo [OK] Node.js %NODEVER% >> "%LOG_FILE%"

:: npm
npm --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] npm 不可用！[0m
    echo [ERROR] npm 不可用 >> "%LOG_FILE%"
    goto error_exit
)
for /f "tokens=*" %%i in ('npm --version 2^>^&1') do set NPMVER=%%i
echo [92m[OK] npm v%NPMVER%[0m
echo [OK] npm v%NPMVER% >> "%LOG_FILE%"
pause

:step_check_frontend
echo.
echo [STEP 6/8] 检查 frontend/ 目录...
echo [%date% %time%] 检查 frontend/ 目录... >> "%LOG_FILE%"
if not exist "frontend\package.json" (
    echo [91m[ERROR] frontend\package.json 不存在！项目结构不完整。[0m
    echo [ERROR] frontend\package.json 不存在 >> "%LOG_FILE%"
    goto error_exit
)
echo [92m[OK] frontend\package.json 存在[0m

:: 检查 node_modules
if not exist "frontend\node_modules" (
    echo [93m[WARN] frontend\node_modules 不存在，正在安装...[0m
    echo [WARN] 安装前端依赖 >> "%LOG_FILE%"
    cd /d "%~dp0frontend"
    call npm install 2>&1 >> "%~dp0%LOG_FILE%"
    cd /d "%~dp0"
    if %ERRORLEVEL% NEQ 0 (
        echo [91m[ERROR] npm install 失败！请手动执行: cd frontend ^&^& npm install[0m
        echo [ERROR] npm install 失败 >> "%LOG_FILE%"
        goto error_exit
    )
    echo [92m[OK] 前端依赖安装完成[0m
    echo [OK] 前端依赖安装完成 >> "%LOG_FILE%"
) else (
    echo [92m[OK] node_modules 已存在[0m
)
pause

:step_start_frontend
echo.
echo [STEP 7/8] 启动前端 Vite 开发服务器...
echo [%date% %time%] 启动前端... >> "%LOG_FILE%"

netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [91m[ERROR] 端口 5173 已被占用！[0m
    echo [ERROR] 端口 5173 已被占用 >> "%LOG_FILE%"
    goto error_exit
)

cd /d "%~dp0frontend"
start "React Frontend" cmd /c "npm run dev 2>&1 >> ..\\vite_output.log"
cd /d "%~dp0"

echo [INFO] Vite 已在后台启动，等待就绪...
echo [INFO] Vite 已启动 >> "%LOG_FILE%"

set /a count=0
:wait_frontend_debug
timeout /t 1 /nobreak >nul
set /a count+=1

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [92m[OK] 前端已就绪 ^(!count! 秒^)[0m
    echo [OK] 前端已就绪 ^(!count! 秒^) >> "%LOG_FILE%"
    goto step_open_browser
)

if %count% GEQ 200 (
    echo [91m[ERROR] 前端 200 秒内未就绪！[0m
    echo [ERROR] 前端超时 >> "%LOG_FILE%"
    echo 请检查 vite_output.log 文件查看错误信息
    goto error_exit
)
goto wait_frontend_debug

:step_open_browser
echo.
echo [STEP 8/8] 启动完成！
echo [%date% %time%] 打开浏览器... >> "%LOG_FILE%"
start http://localhost:5173

echo.
echo ╔══════════════════════════════════════════╗
echo ║  [92m✅ 所有检查通过，系统已启动！[0m            ║
echo ║                                          ║
echo ║  前端: http://localhost:5173              ║
echo ║  后端: http://localhost:5001              ║
echo ║                                          ║
echo ║  预设账户: boss / hr / employee           ║
echo ║  密码均为: 123456                         ║
echo ║                                          ║
echo ║  日志文件: %LOG_FILE%                     ║
echo ║  Flask 日志: flask_output.log             ║
echo ║  Vite 日志:  vite_output.log              ║
echo ╚══════════════════════════════════════════╝
echo [%date% %time%] 启动成功 >> "%LOG_FILE%"
pause
exit /b 0

:error_exit
echo.
echo ╔══════════════════════════════════════════╗
echo ║  [91m❌ 启动失败！请检查上方错误信息。[0m       ║
echo ║                                          ║
echo ║  完整日志: %LOG_FILE%                     ║
echo ╚══════════════════════════════════════════╝
echo [%date% %time%] 启动失败 >> "%LOG_FILE%"
pause
exit /b 1