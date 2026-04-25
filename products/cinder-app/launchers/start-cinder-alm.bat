@echo off
REM ============================================================
REM Cinder — Portable AI Companion (AnythingLLM Edition, Windows)
REM Runs entirely from USB. Never installs anything on the host.
REM ============================================================

title Cinder — Portable AI Companion

set "USB_ROOT=%~dp0"
set "USB_ROOT=%USB_ROOT:~0,-1%"
set "OLLAMA_PORT=11435"

echo.
echo   =========================================
echo    Cinder — Portable AI Companion
echo    AnythingLLM Edition
echo   =========================================
echo.

REM ── Locate Ollama ──────────────────────────────────────
set "OLLAMA_BIN="
if exist "%USB_ROOT%\ollama\windows\ollama.exe" (
    set "OLLAMA_BIN=%USB_ROOT%\ollama\windows\ollama.exe"
)
if "%OLLAMA_BIN%"=="" (
    where ollama >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo   Using system Ollama.
        for /f "delims=" %%i in ('where ollama') do set "OLLAMA_BIN=%%i"
    )
)
if "%OLLAMA_BIN%"=="" (
    echo   ERROR: Ollama not found on USB or system.
    echo   Download from: https://ollama.com/download/windows
    echo   Or place ollama.exe in: %USB_ROOT%\ollama\windows\
    pause
    exit /b 1
)

REM ── Set up model storage on USB ────────────────────────
set "OLLAMA_MODELS=%USB_ROOT%\ollama\models"
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"
set "OLLAMA_HOST=127.0.0.1:%OLLAMA_PORT%"

REM ── Start Ollama if not running ────────────────────────
curl -s "http://127.0.0.1:%OLLAMA_PORT%/api/tags" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   AI engine already running.
    goto :check_model
)
curl -s "http://127.0.0.1:11434/api/tags" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "OLLAMA_PORT=11434"
    set "OLLAMA_HOST=127.0.0.1:11434"
    echo   AI engine already running on default port.
    goto :check_model
)

echo   Starting AI engine...
start /b "" "%OLLAMA_BIN%" serve >nul 2>&1
timeout /t 10 /nobreak >nul

curl -s "http://127.0.0.1:%OLLAMA_PORT%/api/tags" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ERROR: AI engine failed to start.
    pause
    exit /b 1
)
echo   AI engine ready.

:check_model
REM ── Load Cinder model if not present ───────────────────
"%OLLAMA_BIN%" list 2>nul | findstr /i "cinder" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   Loading Cinder model...
    set "MODELFILE="
    if exist "%USB_ROOT%\cinder\Modelfile-final" set "MODELFILE=%USB_ROOT%\cinder\Modelfile-final"
    if exist "%USB_ROOT%\cinder\Modelfile-v3" if "%MODELFILE%"=="" set "MODELFILE=%USB_ROOT%\cinder\Modelfile-v3"

    if defined MODELFILE (
        pushd "%USB_ROOT%\cinder"
        "%OLLAMA_BIN%" create cinder -f "%MODELFILE%"
        popd
        echo   Cinder model loaded.
    ) else (
        echo   No Modelfile found — using base model.
    )
)

REM ── Launch AnythingLLM ─────────────────────────────────
set "STORAGE_DIR=%USB_ROOT%\anythingllm\storage"
if not exist "%STORAGE_DIR%" mkdir "%STORAGE_DIR%"

set "ALM_EXE="
if exist "%USB_ROOT%\anythingllm\AnythingLLM.exe" set "ALM_EXE=%USB_ROOT%\anythingllm\AnythingLLM.exe"
if exist "%USB_ROOT%\anythingllm\AnythingLLMDesktop.exe" set "ALM_EXE=%USB_ROOT%\anythingllm\AnythingLLMDesktop.exe"

REM Check for system-installed AnythingLLM if not on USB
if "%ALM_EXE%"=="" (
    if exist "%LOCALAPPDATA%\Programs\anythingllm-desktop\AnythingLLMDesktop.exe" (
        set "ALM_EXE=%LOCALAPPDATA%\Programs\anythingllm-desktop\AnythingLLMDesktop.exe"
        echo   Using installed AnythingLLM.
    )
)

if "%ALM_EXE%"=="" (
    echo.
    echo   AnythingLLM Desktop not found on USB or system.
    echo.
    echo   Ollama and the Cinder model are ready!
    echo   To complete setup, install AnythingLLM Desktop:
    echo     https://anythingllm.com/download
    echo.
    echo   After installing, run this launcher again.
    echo   Or open AnythingLLM manually and set:
    echo     LLM Provider: Ollama
    echo     Model: cinder
    echo     Ollama URL: http://127.0.0.1:%OLLAMA_PORT%
    echo.
    pause
    exit /b 0
)

echo   Launching Cinder (AnythingLLM)...
echo   Data stored on USB at: %STORAGE_DIR%
echo.

set "LLM_PROVIDER=ollama"
set "OLLAMA_BASE_PATH=http://127.0.0.1:%OLLAMA_PORT%"
start "" "%ALM_EXE%"
