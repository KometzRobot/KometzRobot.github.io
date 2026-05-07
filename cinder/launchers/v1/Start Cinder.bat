@echo off
REM CINDER_LAUNCHER_VERSION=1   bump + republish manifest to push patches

REM ── Self-update: pull launcher patches from manifest on every plug-in. ──
REM Silent on offline/failure. SHA256-verified by PowerShell. Skip with
REM CINDER_NO_SELF_UPDATE=1. The 4 drives that shipped before this hook
REM stay as-is; future flashes inherit the patch path.
if not "%CINDER_NO_SELF_UPDATE%"=="1" (
    if exist "%~dp0Start Cinder.bat.new" del /Q "%~dp0Start Cinder.bat.new" >nul 2>&1
    powershell -nologo -ExecutionPolicy Bypass -command "try { $m = Invoke-RestMethod -Uri 'https://kometzrobot.github.io/cinder/launchers/manifest.json' -TimeoutSec 5; if($m.windows_version -gt 1){ Invoke-WebRequest -Uri $m.windows_url -OutFile '%~dp0Start Cinder.bat.new' -TimeoutSec 30 -UseBasicParsing; $h = (Get-FileHash -Path '%~dp0Start Cinder.bat.new' -Algorithm SHA256).Hash.ToLower(); if($h -ne $m.windows_sha256.ToLower()){ Remove-Item '%~dp0Start Cinder.bat.new' -Force -ErrorAction SilentlyContinue } } } catch {}" >nul 2>&1
    if exist "%~dp0Start Cinder.bat.new" (
        move /Y "%~dp0Start Cinder.bat.new" "%~f0" >nul 2>&1
        if not errorlevel 1 (
            set "CINDER_NO_SELF_UPDATE=1"
            cmd /c ""%~f0""
            exit /b 0
        )
    )
)
REM ────────────────────────────────────────────────────────────────────────

REM ── Cinder Launcher (no-admin scan) ──────────────────────────────────────
set "APP_DRIVE="

for %%d in (D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%d:\Cinder\Windows\Cinder.exe" (
        set "APP_DRIVE=%%d:"
        goto :launch
    )
)

for /f %%d in ('powershell -nologo -command "try{(Get-Volume 'CINDER-APP').DriveLetter}catch{}" 2^>nul') do (
    if not "%%d"=="" (
        if exist "%%d:\Cinder\Windows\Cinder.exe" (
            set "APP_DRIVE=%%d:"
            goto :launch
        )
    )
)

REM Not found without admin — signal VBS to retry with diskpart
exit /b 1

:launch
REM User data lives on CINDERVAULT — the partition the buyer sees as their
REM "vault" — so journals/conversations/memory land where they expect. Fall
REM back to CINDER-APP only when the vault partition isn't mounted yet.
REM
REM Retry up to 6x with a 1s pause: removable-drive auto-mount can lag a few
REM seconds behind Cinder.bat firing. Without this retry, double-clicking
REM the launcher too fast lands user data on CINDER-APP, then CINDERVAULT
REM mounts a moment later, leaving journals stranded on the wrong partition.
set "VAULT_DRIVE="
for /l %%i in (1,1,6) do (
    if not defined VAULT_DRIVE (
        for /f %%d in ('powershell -nologo -command "try{(Get-Volume 'CINDERVAULT').DriveLetter}catch{}" 2^>nul') do (
            if not "%%d"=="" set "VAULT_DRIVE=%%d:"
        )
        if not defined VAULT_DRIVE timeout /t 1 /nobreak >nul
    )
)
if defined VAULT_DRIVE (
    set "STORAGE_DIR=%VAULT_DRIVE%\cinder-data"
    if not exist "%VAULT_DRIVE%\cinder-data" mkdir "%VAULT_DRIVE%\cinder-data"
) else (
    set "STORAGE_DIR=%APP_DRIVE%\Cinder\data"
)
set OLLAMA_HOME=%APP_DRIVE%\Cinder\ollama
set OLLAMA_MODELS=%APP_DRIVE%\Cinder\ollama\models
set OLLAMA_HOST=127.0.0.1:11436
set LLM_PROVIDER=ollama
set OLLAMA_BASE_PATH=http://127.0.0.1:11436
set OLLAMA_MODEL_PREF=cinder
set EMBEDDING_ENGINE=native

REM Verify ollama.exe is actually on the USB before relying on it. A corrupted
REM image flash could land Cinder.exe without ollama, in which case the launcher
REM would silently skip spawn and the buyer would see a blank chat with no clue
REM why. Same fail-loud check Mac and Linux already do.
if not exist "%APP_DRIVE%\Cinder\ollama\ollama.exe" (
    echo.
    echo ERROR: ollama.exe missing from USB at %APP_DRIVE%\Cinder\ollama\
    echo        The image may be corrupted. Re-flash the latest Cinder image.
    pause
    exit /b 0
)

REM Capture ollama startup output so a failed first launch leaves something
REM the buyer can attach to a bug report. `start /b foo > log` only redirects
REM the parent shell, not the spawned child — so wrap the child in `cmd /c`.
set "OLLAMA_LOG=%STORAGE_DIR%\cinder-ollama.log"
if not exist "%STORAGE_DIR%" mkdir "%STORAGE_DIR%" >nul 2>&1

REM Skip ollama startup if our port is already bound (handles double-click).
netstat -an | findstr "127.0.0.1:11436 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    if exist "%OLLAMA_LOG%" move /Y "%OLLAMA_LOG%" "%OLLAMA_LOG%.prev" >nul 2>&1
    start /b "" cmd /c ""%APP_DRIVE%\Cinder\ollama\ollama.exe" serve > "%OLLAMA_LOG%" 2>&1"
)

REM Poll for ollama to come up (up to 10s) instead of a fixed sleep. Slow USB
REM first-launch can take 6-8s before /api/tags responds — a fixed 5s timeout
REM let Cinder.exe load before ollama was ready, leaving the buyer with a
REM blank chat box. Single powershell invocation handles all polling internally
REM to avoid 8x ~500ms PS startup cost. Then verify cinder model is loaded.
set "PRELAUNCH_LOG=%STORAGE_DIR%\cinder-prelaunch.log"
powershell -nologo -command "$ok=$false; for($i=0;$i -lt 10;$i++){try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:11436/api/tags' -UseBasicParsing -TimeoutSec 1; $ok=$true; break}catch{Start-Sleep 1}}; if(-not $ok){Write-Host 'FAIL: ollama not reachable on 127.0.0.1:11436 after 10s'; exit}; if($r.Content -match 'cinder'){Write-Host 'OK: ollama up, cinder model present'}else{Write-Host 'WARN: ollama up but cinder model NOT found in /api/tags. Chat will fail.'}" > "%PRELAUNCH_LOG%" 2>&1

cd /d "%APP_DRIVE%\Cinder\Windows"

REM Block until Cinder closes so we can clean up the ollama we started.
REM Without this, ollama.exe orphans, the USB stays "in use", and Safely
REM Eject fails until the buyer hunts it down in Task Manager.
start /wait "" "Cinder.exe"

REM Kill only the ollama on our isolated port, not any system ollama
REM the buyer runs on 11434 for other apps.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "127.0.0.1:11436 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
REM Always exit 0 so Start Cinder.vbs doesn't interpret a non-zero errorlevel
REM (Cinder window-close exit code, or taskkill-no-match) as a failure and
REM trigger an unwanted UAC re-launch via the diskpart fallback.
exit /b 0
