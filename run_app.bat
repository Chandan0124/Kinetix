@echo off
title Kinetix - High-Speed Phone-to-PC Delta Mirror & Recovery
cd /d "%~dp0"

echo ========================================================
echo   Kinetix - High-Speed Phone-to-PC Delta Mirror ^& Recovery
echo   Engineered for Android 10, 11, 12, 13, 14, 15, 16, 17+
echo ========================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3 is not found in system PATH.
    echo Please install Python 3.10+ from python.org and try again.
    echo.
    pause
    exit /b 1
)

:: Ensure dependencies
echo [*] Checking dependencies...
python -c "import fastapi, uvicorn, starlette, websockets" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing required dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Please run 'pip install -r requirements.txt' manually.
        echo.
        pause
        exit /b 1
    )
)

:: Launch Kinetix Desktop Application
echo [*] Launching Kinetix Desktop Application...
python app.py %*
echo.
echo [*] Kinetix process exited.
pause
