<#
.SYNOPSIS
    One-click uninstaller for MaxHotbox (Autodesk 3ds Max 2026).
.PARAMETER AllUsers
    Also attempt removal from %ProgramData%\Autodesk\ApplicationPlugins.
.PARAMETER RemoveUserConfig
    Delete user custom menu configs and logs without prompting.
.PARAMETER NoPause
    Do not prompt or wait for Enter before exiting.
#>
param(
    [switch]$AllUsers,
    [switch]$RemoveUserConfig,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    $Targets = @(
        (Join-Path $env:APPDATA "Autodesk\ApplicationPlugins\MaxHotbox.bundle")
    )
    if ($AllUsers -or (Test-Path (Join-Path $env:ProgramData "Autodesk\ApplicationPlugins\MaxHotbox.bundle"))) {
        $Targets += (Join-Path $env:ProgramData "Autodesk\ApplicationPlugins\MaxHotbox.bundle")
    }

    $RemovedAny = $false
    foreach ($bundle in ($Targets | Select-Object -Unique)) {
        if (Test-Path $bundle) {
            Remove-Item -Path $bundle -Recurse -Force
            Write-Host "[OK] 已移除插件包: $bundle" -ForegroundColor Green
            $RemovedAny = $true
        }
    }

    if (-not $RemovedAny) {
        Write-Host "[INFO] 未检测到已安装的 MaxHotbox.bundle。" -ForegroundColor Yellow
    }

    $DoCleanConfig = [bool]$RemoveUserConfig
    if (-not $DoCleanConfig -and -not $NoPause) {
        $ans = Read-Host "是否同时清理个人自定义热盒配置与日志? [y/N]"
        if ($ans -match '^[Yy]') {
            $DoCleanConfig = $true
        }
    }

    if ($DoCleanConfig) {
        $ConfigDirs = @(
            (Join-Path $env:LOCALAPPDATA "Autodesk\3dsMax\2026 - 64bit\CHS\userconfig\MaxHotbox"),
            (Join-Path $env:LOCALAPPDATA "Autodesk\3dsMax\2026 - 64bit\ENU\userconfig\MaxHotbox"),
            (Join-Path $env:LOCALAPPDATA "MaxHotbox")
        )
        foreach ($dir in $ConfigDirs) {
            if (Test-Path $dir) {
                Remove-Item -Path $dir -Recurse -Force
                Write-Host "[OK] 已清理用户配置: $dir" -ForegroundColor Green
            }
        }
    }

    $MaxRunning = [bool](Get-Process -Name "3dsmax" -ErrorAction SilentlyContinue)
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [OK] MaxHotbox 卸载完成！" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    if ($MaxRunning) {
        Write-Host "[提示] 检测到 3ds Max 正在运行，请重启 3ds Max 2026 以完全恢复原生四元菜单。" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[ERROR] 卸载失败: $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "按回车键退出" }
    exit 1
}

if (-not $NoPause) { Read-Host "按回车键退出" }
