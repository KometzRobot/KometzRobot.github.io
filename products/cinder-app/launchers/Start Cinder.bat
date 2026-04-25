@echo off
REM ============================================================
REM Cinder — Portable AI Companion (Windows Launcher)
REM Runs entirely from USB. Never installs anything on the host.
REM ============================================================

title Cinder — Starting...
echo.
echo   =========================================
echo    Cinder — Portable AI Companion
echo   =========================================
echo.

set "SCRIPT_DIR=%~dp0"
REM Launcher is at USB root, so USB_ROOT = SCRIPT_DIR
set "USB_ROOT=%SCRIPT_DIR%"
set "OLLAMA_PORT=11435"
set "OLLAMA_HOST=127.0.0.1:%OLLAMA_PORT%"

REM ── Locate portable Ollama binary ──────────────────────
set "OLLAMA_EXE="
if exist "%USB_ROOT%Cinder\bin\windows\ollama.exe" set "OLLAMA_EXE=%USB_ROOT%Cinder\bin\windows\ollama.exe"
if exist "%USB_ROOT%bin\windows\ollama.exe" set "OLLAMA_EXE=%USB_ROOT%bin\windows\ollama.exe"

REM Fallback: check if Ollama is installed on host
if "%OLLAMA_EXE%"=="" (
    where ollama >nul 2>&1
    if %errorlevel%==0 (
        set "OLLAMA_EXE=ollama"
        echo   Using system Ollama installation.
    )
)

if "%OLLAMA_EXE%"=="" (
    echo   ERROR: Ollama not found.
    echo.
    echo   Cinder needs Ollama to run its AI model.
    echo   Install from: https://ollama.com/download/windows
    echo   Or place ollama.exe in: %USB_ROOT%Cinder\bin\windows\
    echo.
    pause
    exit /b 1
)

REM ── Set up model storage on USB ────────────────────────
set "MODELS_DIR=%USB_ROOT%Cinder\models\ollama-data"
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"
set "OLLAMA_MODELS=%MODELS_DIR%"

REM ── Check if engine already running ────────────────────
curl -s "http://127.0.0.1:%OLLAMA_PORT%/api/tags" >nul 2>&1
if %errorlevel%==0 (
    echo   AI engine already running on port %OLLAMA_PORT%.
    goto :load_model
)

REM Also check default port 11434
curl -s "http://127.0.0.1:11434/api/tags" >nul 2>&1
if %errorlevel%==0 (
    set "OLLAMA_PORT=11434"
    echo   AI engine already running on default port.
    goto :load_model
)

REM ── Start Ollama from USB ──────────────────────────────
echo   Starting AI engine...
start /b "" "%OLLAMA_EXE%" serve >"%TEMP%\cinder-ollama.log" 2>&1

REM Wait for it (up to 30 seconds)
set /a "tries=0"
:wait_loop
set /a "tries+=1"
if %tries% gtr 30 (
    echo   ERROR: AI engine failed to start after 30 seconds.
    echo   Check: %TEMP%\cinder-ollama.log
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
curl -s "http://127.0.0.1:%OLLAMA_PORT%/api/tags" >nul 2>&1
if %errorlevel% neq 0 goto :wait_loop
echo   AI engine ready.

:load_model
REM ── Load Cinder model if needed ────────────────────────
"%OLLAMA_EXE%" list 2>nul | findstr /i "cinder" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Loading Cinder model (first time may take a minute)...
    set "MODELFILE="
    if exist "%USB_ROOT%Cinder\Modelfile-v3" set "MODELFILE=%USB_ROOT%Cinder\Modelfile-v3"
    if exist "%USB_ROOT%Cinder\Modelfile-v2" if "%MODELFILE%"=="" set "MODELFILE=%USB_ROOT%Cinder\Modelfile-v2"
    if exist "%USB_ROOT%Cinder\Modelfile" if "%MODELFILE%"=="" set "MODELFILE=%USB_ROOT%Cinder\Modelfile"

    if not "%MODELFILE%"=="" (
        pushd "%USB_ROOT%Cinder\models"
        "%OLLAMA_EXE%" create cinder -f "%MODELFILE%"
        popd
        echo   Model loaded.
    ) else (
        echo   WARNING: No Modelfile found. Using base model.
    )
)

REM ── Launch Cinder app ──────────────────────────────────
echo.

REM Try Windows app in Cinder\Windows
if exist "%USB_ROOT%Cinder\Windows\Cinder.exe" (
    echo   Launching Cinder...
    start "" "%USB_ROOT%Cinder\Windows\Cinder.exe"
    goto :done
)

REM Try in dist folder (old layout)
if exist "%USB_ROOT%dist\win-unpacked\Cinder.exe" (
    echo   Launching Cinder...
    start "" "%USB_ROOT%dist\win-unpacked\Cinder.exe"
    goto :done
)

echo   ERROR: Could not find Cinder.exe
echo   Checked: %USB_ROOT%Cinder\Windows\
pause
exit /b 1

:done
echo   Cinder is running. Close this window when done.
echo   (The AI engine will shut down automatically.)
echo.
pause
REM Clean shutdown — kill the portable Ollama we started
taskkill /f /im ollama.exe >nul 2>&1
