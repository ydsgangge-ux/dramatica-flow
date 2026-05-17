@echo off
title Dramatica-Flow Web UI
cd /d %~dp0
echo ========================================
echo   Dramatica-Flow Web UI
echo ========================================
echo.
echo Starting server...
echo Access URL: http://localhost:8766
echo.
start /b python -m uvicorn core.server:app --reload --port 8766

timeout /t 3 /nobreak >nul
start http://localhost:8766

echo.
echo Server is running in background. Press any key to exit this window.
echo.
pause >nul
