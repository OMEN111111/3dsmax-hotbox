@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%uninstall.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%uninstall.ps1" %*
) else if exist "%SCRIPT_DIR%..\packaging\uninstall.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%..\packaging\uninstall.ps1" %*
) else (
    echo [ERROR] uninstall.ps1 not found.
    pause
    exit /b 1
)
endlocal
