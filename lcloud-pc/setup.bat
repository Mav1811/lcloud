@echo off
setlocal enabledelayedexpansion
echo ================================================
echo   Lcloud PC App - Setup Script
echo   Version 0.1.0
echo ================================================
echo.

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.12 from:
    echo   https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe
    echo.
    echo IMPORTANT: During install, check "Add Python to PATH"
    echo Then run this script again.
    pause
    exit /b 1
)

echo [OK] Python found
python --version

echo.
echo Creating virtual environment in .\venv ...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment created

echo.
echo Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Setup complete!
echo   Run "run.bat" to start Lcloud.
echo ================================================
pause
