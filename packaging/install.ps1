<#
.SYNOPSIS
    Installs MaxHotbox.bundle for Autodesk 3ds Max 2026.
.PARAMETER AllUsers
    Install to %ProgramData%\Autodesk\ApplicationPlugins (requires Administrator).
    Default installs to %APPDATA%\Autodesk\ApplicationPlugins (current user).
.PARAMETER NoPause
    Do not wait for Enter before exiting.
#>
param(
    [switch]$AllUsers,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $CandidatePaths = @(
        (Join-Path $ScriptDir "MaxHotbox.bundle"),
        (Join-Path (Split-Path -Parent $ScriptDir) "dist\MaxHotbox.bundle")
    )

    $SourceBundle = $CandidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $SourceBundle) {
        throw "未找到 MaxHotbox.bundle。请先运行 python packaging/build_package.py 或在 dist/ 解压目录中执行安装。"
    }

    if ($AllUsers) {
        $TargetRoot = Join-Path $env:ProgramData "Autodesk\ApplicationPlugins"
    } else {
        $TargetRoot = Join-Path $env:APPDATA "Autodesk\ApplicationPlugins"
    }

    $TargetBundle = Join-Path $TargetRoot "MaxHotbox.bundle"

    if (-not (Test-Path $TargetRoot)) {
        New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
    }

    if (Test-Path $TargetBundle) {
        Write-Host "[INFO] 正在覆盖旧版本: $TargetBundle" -ForegroundColor Yellow
        Remove-Item -Path $TargetBundle -Recurse -Force
    }

    Write-Host "[INFO] 正在安装 MaxHotbox.bundle 到: $TargetBundle" -ForegroundColor Cyan
    Copy-Item -Path $SourceBundle -Destination $TargetBundle -Recurse -Force

    # Verify critical files exist
    $Required = @(
        (Join-Path $TargetBundle "PackageContents.xml"),
        (Join-Path $TargetBundle "Contents\macroscripts\MaxHotbox.mcr"),
        (Join-Path $TargetBundle "Contents\scripts\post_startup.ms"),
        (Join-Path $TargetBundle "Contents\python\max_hotbox\controller.py")
    )
    foreach ($req in $Required) {
        if (-not (Test-Path $req)) {
            throw "安装校验失败，缺少文件: $req"
        }
    }

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [OK] MaxHotbox for 3ds Max 2026 安装成功！" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "安装路径 : $TargetBundle"
    Write-Host ""
    Write-Host "如何生效:" -ForegroundColor Yellow
    Write-Host "  1. 重启 Autodesk 3ds Max 2026（推荐），重启后将自动挂载视口并在顶部出现 [MaxHotbox] 菜单。"
    Write-Host "  2. 如果 Max 2026 已经打开不想重启，可在 Max 顶部菜单点击:"
    Write-Host "     [脚本 -> 运行脚本...] 选择 Load_MaxHotbox_Now.ms 立即激活！"
    Write-Host ""
    Write-Host "默认操作方式（在任意 3D 视口内）:" -ForegroundColor Cyan
    Write-Host "  - 按住 右键 / Shift+右键 / Ctrl+右键 / Alt+右键 -> 划动方向 -> 松开执行"
    Write-Host "  - 按住 `` (Tab上方反引号键) -> 呼出五区全局热盒"
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "[ERROR] 安装失败: $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) {
        Read-Host "按回车键退出"
    }
    exit 1
}

if (-not $NoPause) {
    Read-Host "按回车键退出"
}
