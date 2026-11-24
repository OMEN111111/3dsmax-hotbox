@echo off
chcp 65001 >nul
setlocal
title MaxHotbox Manager (3ds Max 2026 / 2027)
set "ROOT_DIR=%~dp0"
if exist "%ROOT_DIR%manager.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%manager.ps1" -BaseDir "%ROOT_DIR%." %*
) else if exist "%ROOT_DIR%packaging\manager.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%packaging\manager.ps1" -BaseDir "%ROOT_DIR%." %*
) else if exist "%ROOT_DIR%..\packaging\manager.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%..\packaging\manager.ps1" -BaseDir "%ROOT_DIR%.." %*
) else (
    echo [ERROR] manager.ps1 not found.
    pause
    exit /b 1
)
set "EC=%ERRORLEVEL%"
endlocal & exit /b %EC%
