@echo off
echo ============================================
echo  Screen Recorder - Dependency Installer
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing required packages...
echo.
pip install -r requirements.txt

echo.
echo ============================================
echo  Done! Run the app with:  python main.py
echo  Or double-click:         run.bat
echo ============================================
pause
