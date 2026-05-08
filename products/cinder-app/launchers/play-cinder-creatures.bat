@echo off
REM Cinder Creatures - opens the GB-style creature collector in default browser.
set GAME=%~dp0games\cinder-creatures.html
if not exist "%GAME%" (
  echo [cinder-creatures] missing %GAME%
  pause
  exit /b 1
)
start "" "%GAME%"
