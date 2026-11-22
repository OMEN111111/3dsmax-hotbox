@echo off
chcp 65001 >nul
setlocal
set "ROOT_DIR=%~dp0"
if exist "%ROOT_DIR%install.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%install.ps1" %*
) else if exist "%ROOT_DIR%packaging\install.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%packaging\install.ps1" %*
) else if exist "%ROOT_DIR%..\packaging\install.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%..\packaging\install.ps1" %*
) else (
    echo [ERROR] install.ps1 not found.
    pause
    exit /b 1
)
endlocal
