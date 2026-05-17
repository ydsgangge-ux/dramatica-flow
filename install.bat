@echo off
setlocal enabledelayedexpansion
title Dramatica-Flow Install
cd /d %~dp0

echo.
echo  ====================================================
echo         Dramatica-Flow Installer
echo         AI Novel Writing System
echo  ====================================================
echo.

:: -- Step 1: Check Python --
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found!
    echo.
    echo   Please install Python 3.11+ from:
    echo   https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo       Python %PY_VER%

for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 goto :py_old
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 goto :py_old
echo       Version OK (3.11+ required)
goto :py_ok

:py_old
echo.
echo [ERROR] Python %PY_VER% is too old. Python 3.11+ required.
echo.
echo   Download: https://www.python.org/downloads/
echo.
pause
exit /b 1
:py_ok

:: -- Step 2: Install project --
echo.
echo [2/5] Installing project and dependencies...
python -m pip install -e . --quiet
if %ERRORLEVEL% neq 0 (
    echo [WARN] install failed, installing packages directly...
    python -m pip install openai pydantic typer rich python-dotenv fastapi uvicorn python-multipart --quiet
)

:: -- Step 3: Verify ALL dependencies --
echo.
echo [3/5] Verifying all dependencies...
set ALL_OK=1

for %%M in (openai pydantic fastapi uvicorn typer rich dotenv) do (
    python -c "import %%M" >nul 2>nul
    if !ERRORLEVEL! neq 0 (
        echo       [MISSING] %%M
        python -m pip install %%M --quiet
        set ALL_OK=0
    )
)

python -c "import multipart" >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo       [MISSING] python-multipart
    python -m pip install python-multipart --quiet
    set ALL_OK=0
)

if !ALL_OK!==1 (
    echo       All dependencies installed.
)

where df >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo       CLI command "df" is available
) else (
    echo       [TIP] CLI command "df" not in PATH. You can use Web UI instead.
)

:: -- Step 4: Create .env --
echo.
echo [4/5] Checking config file...
if exist .env (
    echo       .env already exists, skipped.
) else if exist .env.example (
    copy .env.example .env >nul
    echo       Created .env from .env.example
) else (
    echo # Dramatica-Flow Config> .env
    echo LLM_PROVIDER=deepseek>> .env
    echo.>> .env
    echo # DeepSeek API (replace sk-xxx with your real key)>> .env
    echo DEEPSEEK_API_KEY=sk-xxx>> .env
    echo DEEPSEEK_BASE_URL=https://api.deepseek.com/v1>> .env
    echo DEEPSEEK_MODEL=deepseek-chat>> .env
    echo.>> .env
    echo # Ollama local model (free)>> .env
    echo # LLM_PROVIDER=ollama>> .env
    echo # OLLAMA_BASE_URL=http://localhost:11434/v1>> .env
    echo # OLLAMA_MODEL=llama3.1>> .env
    echo       Created .env file
)

:: -- Step 5: Create launch script --
echo.
echo [5/5] Creating startup script...
echo @echo off> launch_web.bat
echo cd /d "%%~dp0">> launch_web.bat
echo title Dramatica-Flow Web UI>> launch_web.bat
echo echo.>> launch_web.bat
echo echo   Starting Dramatica-Flow...>> launch_web.bat
echo echo   Open: http://localhost:8766>> launch_web.bat
echo echo.>> launch_web.bat
echo start http://localhost:8766>> launch_web.bat
echo python -m uvicorn core.server:app --reload --port 8766>> launch_web.bat
echo if errorlevel 1 pause>> launch_web.bat
echo       Created: launch_web.bat

:: -- Done --
echo.
echo ====================================================
echo  Installation complete!
echo.
echo  How to start:
echo    Double-click "launch_web.bat"
echo    Open browser: http://localhost:8766
echo.
echo  === MUST configure AI backend (choose one) ===
echo.
echo  Option A: DeepSeek API (best quality, paid)
echo    1. Register at https://platform.deepseek.com
echo    2. Get your API Key
echo    3. Open .env with Notepad
echo    4. Replace "sk-xxx" with your real API Key
echo.
echo  Option B: Ollama local model (free)
echo    1. Download from https://ollama.ai
echo    2. Run: ollama pull qwen2.5
echo    3. Open .env, change LLM_PROVIDER to ollama
echo.
echo ====================================================
echo.
pause
