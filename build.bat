@echo off
cd /d "%~dp0"
echo ============================================
echo   Screen Recorder -- Build Installer
echo ============================================
echo.
echo This will:
echo   1. Bundle Python + all packages into exe
echo   2. Bundle FFmpeg inside the exe
echo   3. Create ScreenRecorderSetup.exe
echo.
echo (First build takes 3-5 minutes)
echo.

python build.py

if errorlevel 1 (
    echo.
    echo Build FAILED. See errors above.
    pause
    exit /b 1
)

pause
