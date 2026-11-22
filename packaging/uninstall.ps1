<#
.SYNOPSIS
    Uninstalls MaxHotbox.bundle for Autodesk 3ds Max 2026.
.PARAMETER AllUsers
    Remove from %ProgramData%\Autodesk\ApplicationPlugins (requires Administrator).
.PARAMETER RemoveUserConfig
    Also delete user custom menu configs and logs.
.PARAMETER NoPause
    Do not wait for Enter before exiting.
#>
param(
    [switch]$AllUsers,
    [switch]$RemoveUserConfig,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    if ($AllUsers) {
        $TargetBundle = Join-Path $env:ProgramData "Autodesk\ApplicationPlugins\MaxHotbox.bundle"
    } else {
        $TargetBundle = Join-Path $env:APPDATA "Autodesk\ApplicationPlugins\MaxHotbox.bundle"
    }

    if (Test-Path $TargetBundle) {
        Remove-Item -Path $TargetBundle -Recurse -Force
        Write-Host "[OK] 已删除插件包: $TargetBundle" -ForegroundColor Green
    } else {
        Write-Host "[INFO] 未检测到已安装的插件包: $TargetBundle" -ForegroundColor Yellow
    }

    if ($RemoveUserConfig) {
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

    Write-Host "卸载完成。如 3ds Max 2026 正在运行，请重启以完全恢复原生状态。" -ForegroundColor Cyan
}
catch {
    Write-Host "[ERROR] 卸载失败: $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) {
        Read-Host "按回车键退出"
    }
    exit 1
}

if (-not $NoPause) {
    Read-Host "按回车键退出"
}
