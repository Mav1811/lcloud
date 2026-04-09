@echo off
cd /d "%~dp0"
echo ================================================
echo   Lcloud Android — Build APK
echo ================================================
echo.

set FLUTTER=H:\fun\tools\flutter\bin\flutter.bat

if not exist "%FLUTTER%" (
    echo [ERROR] Flutter not found at H:\fun\tools\flutter
    echo Run tools\install_flutter.bat first.
    pause
    exit /b 1
)

echo Building release APK...
cd lcloud-android
call "%FLUTTER%" build apk --release

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause
    exit /b 1
)

REM Copy APK to project root for easy access
copy /y "build\app\outputs\flutter-apk\app-release.apk" "..\lcloud-android.apk" >nul

echo.
echo ================================================
echo   APK built: lcloud-android.apk
echo   Size:
for %%F in ("..\lcloud-android.apk") do echo   %%~zF bytes
echo.
echo   To install on phone, run: install-android.bat
echo ================================================
pause
