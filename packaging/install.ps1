<#
.SYNOPSIS
    One-click installer for MaxHotbox (Autodesk 3ds Max 2026).
    Works both from an extracted release ZIP and directly from a GitHub source clone.
.PARAMETER AllUsers
    Install to %ProgramData%\Autodesk\ApplicationPlugins (requires Administrator).
.PARAMETER NoPause
    Do not wait for Enter before exiting.
#>
param(
    [switch]$AllUsers,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Copy-WithUtf8Bom {
    param([string]$Src, [string]$Dst)
    $text = [System.IO.File]::ReadAllText($Src, [System.Text.Encoding]::UTF8)
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    $parent = Split-Path -Parent $Dst
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($Dst, $text, $utf8Bom)
}

try {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $ScriptDir

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

    $CandidateBundles = @(
        (Join-Path $ScriptDir "MaxHotbox.bundle"),
        (Join-Path $RepoRoot "dist\MaxHotbox.bundle")
    )
    $SourceBundle = $CandidateBundles | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($SourceBundle) {
        Write-Host "[INFO] 正在从插件包安装 MaxHotbox.bundle 到: $TargetBundle" -ForegroundColor Cyan
        Copy-Item -Path $SourceBundle -Destination $TargetBundle -Recurse -Force
    }
    elseif ((Test-Path (Join-Path $RepoRoot "src\max_hotbox")) -and (Test-Path (Join-Path $RepoRoot "packaging\PackageContents.xml"))) {
        Write-Host "[INFO] 检测到源码目录，正在直接组装并安装 MaxHotbox.bundle 到: $TargetBundle" -ForegroundColor Cyan
        $Contents = Join-Path $TargetBundle "Contents"
        New-Item -ItemType Directory -Path (Join-Path $Contents "macroscripts") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $Contents "scripts") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $Contents "python") -Force | Out-Null

        Copy-Item (Join-Path $RepoRoot "packaging\PackageContents.xml") (Join-Path $TargetBundle "PackageContents.xml") -Force
        Copy-WithUtf8Bom (Join-Path $RepoRoot "src\maxscript\MaxHotbox.mcr") (Join-Path $Contents "macroscripts\MaxHotbox.mcr")
        Copy-WithUtf8Bom (Join-Path $RepoRoot "src\maxscript\post_startup.ms") (Join-Path $Contents "scripts\post_startup.ms")
        Copy-WithUtf8Bom (Join-Path $RepoRoot "src\maxscript\uninstall_helper.ms") (Join-Path $Contents "scripts\uninstall_helper.ms")
        Copy-Item (Join-Path $RepoRoot "src\max_hotbox") (Join-Path $Contents "python\max_hotbox") -Recurse -Force
        Get-ChildItem -Path (Join-Path $Contents "python\max_hotbox") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    }
    else {
        throw "未找到 MaxHotbox.bundle 或插件源码目录。"
    }

    # Verify critical files
    $Required = @(
        (Join-Path $TargetBundle "PackageContents.xml"),
        (Join-Path $TargetBundle "Contents\macroscripts\MaxHotbox.mcr"),
        (Join-Path $TargetBundle "Contents\scripts\post_startup.ms"),
        (Join-Path $TargetBundle "Contents\python\max_hotbox\controller.py"),
        (Join-Path $TargetBundle "Contents\python\max_hotbox\graphite_tools.py")
    )
    foreach ($req in $Required) {
        if (-not (Test-Path $req)) {
            throw "安装校验失败，缺少文件: $req"
        }
    }

    $MaxRunning = [bool](Get-Process -Name "3dsmax" -ErrorAction SilentlyContinue)

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [OK] MaxHotbox v0.1.1 (3ds Max 2026) 一键安装成功！" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "安装路径 : $TargetBundle"
    Write-Host ""
    if ($MaxRunning) {
        Write-Host "[提示] 检测到 3ds Max 正在运行:" -ForegroundColor Yellow
        Write-Host "  - 方式 A (免重启): 在 Max 顶部点击 [脚本 -> 运行脚本...] 选择 Load_MaxHotbox_Now.ms 立即热重载激活！"
        Write-Host "  - 方式 B (推荐)  : 重启 3ds Max 2026 即可自动生效。"
    } else {
        Write-Host "[提示] 请直接启动 Autodesk 3ds Max 2026，顶部菜单栏将自动出现 [MaxHotbox] 按钮。" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "默认操作方式（在任意 3D 视口内）:" -ForegroundColor Cyan
    Write-Host "  - 右键 / Shift+右键 / Ctrl+右键 / Alt+右键 / 空格+右键 : 划动执行（右侧 □ 为参数面板）"
    Write-Host "  - 悬停带 ▸ 按钮展开二级菜单；悬停下方 [‹ 返回上级] 或轻点左键返回上级"
    Write-Host "  - 按住 `` (Tab上方反引号键) : 呼出五区全局热盒"
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "[ERROR] 安装失败: $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "按回车键退出" }
    exit 1
}

if (-not $NoPause) { Read-Host "按回车键退出" }
