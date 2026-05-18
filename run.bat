@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo The app exited with an error.
    echo Run install.bat if you haven't installed dependencies yet.
    pause
)
