@echo off
title Nabil Video Studio Pro
cd /d "%~dp0"

:: Check if first run setup is needed
if not exist "setup_complete.flag" (
    echo ============================================================
    echo   FIRST TIME SETUP REQUIRED
    echo ============================================================
    echo.
    echo   AI components need to be downloaded (3-4 GB).
    echo   This only happens once.
    echo.
    echo   Press any key to start setup...
    pause > nul
    python\python.exe first_run_setup.py
)

:: Launch the main application
echo Starting Nabil Video Studio Pro...
start "" python\pythonw.exe ui_modern.py
