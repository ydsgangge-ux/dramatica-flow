@echo off
title Dramatica-Flow Server
cd /d %~dp0
echo ========================================
echo   Dramatica-Flow Web UI Server
echo ========================================
echo.
echo Starting server...
echo Access URL: http://localhost:8766
echo.
echo Press Ctrl+C to stop server
echo.
python -m uvicorn core.server:app --reload --port 8766

if errorlevel 1 (
    echo.
    echo Startup failed! Please check error messages.
    echo.
    pause
)
