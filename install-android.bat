@echo off
cd /d "%~dp0"
echo ================================================
echo   Lcloud Android — Install APK to Phone
echo ================================================
echo.

REM Check ADB is available
set ADB=C:\Users\%USERNAME%\AppData\Local\Android\Sdk\platform-tools\adb.exe
if not exist "%ADB%" (
    echo [ERROR] ADB not found at: %ADB%
    echo.
    echo Please make sure Android SDK Platform-Tools is installed.
    echo Or update the ADB path in this script.
    pause
    exit /b 1
)

REM Check phone is connected
echo Checking for connected device...
"%ADB%" devices
echo.

"%ADB%" get-state >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No Android device detected.
    echo.
    echo Steps to connect your phone:
    echo   1. Connect phone to PC via USB cable
    echo   2. On phone: Settings ^> Developer Options ^> Enable USB Debugging
    echo   3. Accept the "Allow USB debugging?" prompt on your phone
    echo   4. Run this script again
    echo.
    echo NOTE: Developer Options is hidden by default.
    echo   Go to Settings ^> About Phone ^> tap "Build Number" 7 times to unlock it.
    pause
    exit /b 1
)

echo [OK] Device connected. Installing Lcloud...
echo.
"%ADB%" install -r lcloud-android.apk

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed.
    echo Try: disconnect USB, reconnect, and run again.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Lcloud installed successfully!
echo.
echo   Open the Lcloud app on your phone.
echo   Make sure your PC and phone are on the same WiFi.
echo   Start Lcloud on your PC (run.bat), then tap Backup Now.
echo ================================================
pause
