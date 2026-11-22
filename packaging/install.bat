@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%install.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
) else if exist "%SCRIPT_DIR%..\packaging\install.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%..\packaging\install.ps1" %*
) else (
    echo [ERROR] install.ps1 not found.
    pause
    exit /b 1
)
endlocal
