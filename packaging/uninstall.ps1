<#
.SYNOPSIS
    CLI uninstaller wrapper for MaxHotbox (Autodesk 3ds Max 2026 / 2027).
    Delegates to manager.ps1.
#>
param(
    [ValidateSet("2026", "2027", "All")]
    [string]$MaxVersion = "All",
    [switch]$AllUsers,
    [switch]$RemoveUserConfig,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manager = Join-Path $ScriptDir "manager.ps1"
if (-not (Test-Path $Manager)) {
    throw "未找到 manager.ps1: $Manager"
}

& $Manager -Action Uninstall -TargetVersions $MaxVersion -AllUsers:$AllUsers -RemoveUserConfig:$RemoveUserConfig -NoPause:$NoPause
exit $LASTEXITCODE
