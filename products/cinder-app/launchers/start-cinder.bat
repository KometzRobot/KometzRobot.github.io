@echo off
title Cinder AI Companion
echo.
echo  ╔══════════════════════════════════╗
echo  ║   CINDER - Local AI Companion   ║
echo  ║   No cloud. No tracking.        ║
echo  ║   Your conversations stay here. ║
echo  ╚══════════════════════════════════╝
echo.
echo Starting Cinder... (this may take 30 seconds on first run)
echo.

:: Find the llamafile in the same directory or parent
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%cinder.llamafile.exe" (
    set "CINDER=%SCRIPT_DIR%cinder.llamafile.exe"
) else if exist "%SCRIPT_DIR%..\cinder.llamafile.exe" (
    set "CINDER=%SCRIPT_DIR%..\cinder.llamafile.exe"
) else (
    echo ERROR: cinder.llamafile.exe not found!
    echo Make sure cinder.llamafile is renamed to cinder.llamafile.exe on Windows.
    pause
    exit /b 1
)

:: Run in chat mode with system prompt
"%CINDER%" --chat -m cinder.gguf -ngl 35 -c 8192 --system-prompt "You are Cinder — a local AI companion. Be warm, direct, honest. Have opinions. No cloud, no tracking."

echo.
echo Cinder has stopped. Press any key to exit.
pause >nul
