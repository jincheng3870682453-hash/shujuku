@echo off
title Dynamic Registry Launcher

echo ========================================
echo  Dynamic Registry System Launcher
echo ========================================
echo.
echo  [1] Web Mode (Browser)
echo  [2] Desktop Mode (Electron)
echo  [3] Install Dependencies
echo  [0] Exit
echo.
set /p choice="Enter your choice (0-3): "

if "%choice%"=="0" exit /b
if "%choice%"=="1" goto web
if "%choice%"=="2" goto desktop
if "%choice%"=="3" goto install
goto menu

:web
echo Starting Web Mode...
start /B python app.py
timeout /t 2 /nobreak >nul
cd /d frontend
start /B npm run dev
timeout /t 3 /nobreak >nul
start http://localhost:5173
echo Browser opened at http://localhost:5173
pause
exit /b

:desktop
echo Starting Desktop Mode...
start /B python app.py
timeout /t 2 /nobreak >nul
cd /d frontend
start /B npm run dev
timeout /t 3 /nobreak >nul
cd /d electron
start /B npm start
echo Electron window launched.
pause
exit /b

:install
echo Installing Python dependencies...
pip install -r requirements.txt
echo Installing frontend dependencies...
cd /d frontend
npm install
echo Installing Electron dependencies...
cd /d ../electron
npm install
echo All dependencies installed.
pause
exit /b