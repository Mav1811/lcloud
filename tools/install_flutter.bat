@echo off
setlocal enabledelayedexpansion
echo ================================================
echo   Flutter SDK Installer for Lcloud
echo   Installs Flutter to H:\fun\tools\flutter
echo ================================================
echo.

REM Check Git is available
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed. Install from https://git-scm.com
    pause
    exit /b 1
)

set FLUTTER_DIR=H:\fun\tools\flutter

if exist "%FLUTTER_DIR%" (
    echo [INFO] Flutter already exists at %FLUTTER_DIR%
    echo If you want to reinstall, delete that folder and run this again.
    pause
    exit /b 0
)

echo Cloning Flutter stable (this may take a few minutes)...
git clone https://github.com/flutter/flutter.git -b stable "%FLUTTER_DIR%" --depth=1

if errorlevel 1 (
    echo [ERROR] Failed to clone Flutter.
    pause
    exit /b 1
)

echo.
echo Adding Flutter to PATH for this session...
set PATH=%FLUTTER_DIR%\bin;%PATH%

echo Running flutter doctor...
"%FLUTTER_DIR%\bin\flutter.bat" doctor

echo.
echo ================================================
echo   Flutter installed to: %FLUTTER_DIR%
echo.
echo   IMPORTANT: Add to your PATH permanently:
echo   H:\fun\tools\flutter\bin
echo.
echo   In Windows: Search "Environment Variables"
echo   → System Variables → Path → New
echo   → Paste: H:\fun\tools\flutter\bin
echo ================================================
pause
