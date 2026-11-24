<#
.SYNOPSIS
    MaxHotbox Unified Multi-Version Manager for Autodesk 3ds Max 2026 / 2027.
    Provides an interactive numbered menu (via MaxHotbox_Manager.bat) and CLI actions:
      - Install plugin separately for 3ds Max 2026, 2027, or both
      - Uninstall plugin separately for 3ds Max 2026, 2027, or both
      - Check GitHub latest release and download assets locally (with SHA-256 verification)
      - Update already-installed Max versions (online or local)
#>
param(
    [ValidateSet("Menu", "Status", "Install", "Uninstall", "CheckUpdate", "DownloadUpdate", "UpdateInstalled")]
    [string]$Action = "Menu",

    [string]$TargetVersions = "",

    [string]$BaseDir = "",

    [string]$SourceDir = "",

    [string]$DownloadDir = "",

    [string]$InstallRoot = "",

    [switch]$AllUsers,

    [switch]$RemoveUserConfig,

    [switch]$UseOnlineUpdate,

    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
try {
    $Host.UI.RawUI.WindowTitle = "MaxHotbox 多版本插件管理器 (3ds Max 2026 / 2027)"
} catch {}
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {}

# ------------------------------------------------------------------ Constants
$script:PluginName = "MaxHotbox"
$script:GitHubRepo = "OMEN111111/3dsmax-hotbox"
$script:SupportedYears = @(2026, 2027)

$script:ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($BaseDir)) {
    if ((Split-Path -Leaf $script:ScriptDir) -ieq "packaging") {
        $script:WorkRoot = Split-Path -Parent $script:ScriptDir
    } else {
        $script:WorkRoot = $script:ScriptDir
    }
} else {
    $script:WorkRoot = (Resolve-Path $BaseDir).Path
}

if ([string]::IsNullOrWhiteSpace($DownloadDir)) {
    $script:DownloadsRoot = Join-Path $script:WorkRoot "downloads"
} else {
    $script:DownloadsRoot = $DownloadDir
}

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    if ($AllUsers) {
        $script:PrimaryPluginsRoot = Join-Path $env:ProgramData "Autodesk\ApplicationPlugins"
    } else {
        $script:PrimaryPluginsRoot = Join-Path $env:APPDATA "Autodesk\ApplicationPlugins"
    }
} else {
    $script:PrimaryPluginsRoot = $InstallRoot
}

# -------------------------------------------------------------------- Helpers
function Copy-WithUtf8Bom {
    param([string]$Src, [string]$Dst)
    $text = [System.IO.File]::ReadAllText($Src, [System.Text.Encoding]::UTF8)
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    $parent = Split-Path -Parent $Dst
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($Dst, $text, $utf8Bom)
}

function Parse-VersionTuple {
    param([string]$Ver)
    if ([string]::IsNullOrWhiteSpace($Ver)) { return [version]"0.0.0" }
    $clean = ($Ver.Trim() -replace '^[vV]', '')
    if ($clean -match '^(\d+)\.(\d+)(?:\.(\d+))?') {
        $maj = [int]$Matches[1]
        $min = [int]$Matches[2]
        $pat = if ($Matches[3]) { [int]$Matches[3] } else { 0 }
        return [version]::new($maj, $min, $pat)
    }
    return [version]"0.0.0"
}

function Compare-PluginVersion {
    param([string]$A, [string]$B)
    $va = Parse-VersionTuple $A
    $vb = Parse-VersionTuple $B
    return $va.CompareTo($vb)
}

function Get-BundleMetadata {
    param([string]$BundlePath)
    $xmlPath = Join-Path $BundlePath "PackageContents.xml"
    if (-not (Test-Path $xmlPath)) { return $null }
    try {
        [xml]$doc = Get-Content -Path $xmlPath -Raw -Encoding UTF8
        $pkg = $doc.ApplicationPackage
        $ver = [string]$pkg.AppVersion
        $reqs = $doc.SelectNodes("//RuntimeRequirements")
        $minYear = 9999
        $maxYear = 0
        foreach ($r in $reqs) {
            $sMin = [string]$r.GetAttribute("SeriesMin")
            $sMax = [string]$r.GetAttribute("SeriesMax")
            if ($sMin -match '^(\d{4})') {
                $y = [int]$Matches[1]
                if ($y -lt $minYear) { $minYear = $y }
            }
            if ($sMax -match '^(\d{4})') {
                $y = [int]$Matches[1]
                if ($y -gt $maxYear) { $maxYear = $y }
            }
        }
        if ($minYear -eq 9999) { $minYear = 2026 }
        if ($maxYear -eq 0) { $maxYear = $minYear }
        return [PSCustomObject]@{
            Path      = $BundlePath
            Version   = $ver
            SeriesMin = $minYear
            SeriesMax = $maxYear
        }
    } catch {
        return $null
    }
}

function Get-SourceVersion {
    param([PSCustomObject]$Source)
    if ($null -eq $Source) { return "未知" }
    if ($Source.Kind -eq "bundle") {
        $meta = Get-BundleMetadata $Source.Path
        if ($meta) { return $meta.Version }
    } elseif ($Source.Kind -eq "repo") {
        $constFile = Join-Path $Source.Path "src\max_hotbox\constants.py"
        if (Test-Path $constFile) {
            $txt = Get-Content -Path $constFile -Raw -Encoding UTF8
            if ($txt -match 'PLUGIN_VERSION\s*=\s*"([^"]+)"') {
                return $Matches[1]
            }
        }
        $xmlFile = Join-Path $Source.Path "packaging\PackageContents.xml"
        if (Test-Path $xmlFile) {
            [xml]$doc = Get-Content -Path $xmlFile -Raw -Encoding UTF8
            return [string]$doc.ApplicationPackage.AppVersion
        }
    }
    return "未知"
}

function Resolve-InstallSource {
    param([string]$OverrideDir = "")

    if (-not [string]::IsNullOrWhiteSpace($OverrideDir)) {
        if (Test-Path (Join-Path $OverrideDir "PackageContents.xml")) {
            return [PSCustomObject]@{ Kind = "bundle"; Path = $OverrideDir; Label = $OverrideDir }
        }
        $subBundle = Join-Path $OverrideDir "MaxHotbox.bundle"
        if (Test-Path (Join-Path $subBundle "PackageContents.xml")) {
            return [PSCustomObject]@{ Kind = "bundle"; Path = $subBundle; Label = $subBundle }
        }
        if ((Test-Path (Join-Path $OverrideDir "src\max_hotbox")) -and (Test-Path (Join-Path $OverrideDir "packaging\PackageContents.xml"))) {
            return [PSCustomObject]@{ Kind = "repo"; Path = $OverrideDir; Label = "源码目录 ($OverrideDir)" }
        }
        throw "指定的源目录不包含有效的 MaxHotbox.bundle 或源码结构: $OverrideDir"
    }

    $candidates = @(
        (Join-Path $script:WorkRoot "MaxHotbox.bundle"),
        (Join-Path $script:ScriptDir "MaxHotbox.bundle"),
        (Join-Path $script:WorkRoot "dist\MaxHotbox.bundle")
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "PackageContents.xml")) {
            return [PSCustomObject]@{ Kind = "bundle"; Path = $c; Label = $c }
        }
    }

    if ((Test-Path (Join-Path $script:WorkRoot "src\max_hotbox")) -and (Test-Path (Join-Path $script:WorkRoot "packaging\PackageContents.xml"))) {
        return [PSCustomObject]@{ Kind = "repo"; Path = $script:WorkRoot; Label = "源码目录 ($($script:WorkRoot))" }
    }

    return $null
}

function Find-LatestDownloadedSource {
    if (-not (Test-Path $script:DownloadsRoot)) { return $null }
    $best = $null
    $bestVer = [version]"0.0.0"
    foreach ($dir in (Get-ChildItem -Path $script:DownloadsRoot -Directory -ErrorAction SilentlyContinue)) {
        $bundleCand = Join-Path $dir.FullName "extracted\MaxHotbox.bundle"
        if (-not (Test-Path (Join-Path $bundleCand "PackageContents.xml"))) {
            $bundleCand = Join-Path $dir.FullName "MaxHotbox.bundle"
        }
        if (Test-Path (Join-Path $bundleCand "PackageContents.xml")) {
            $meta = Get-BundleMetadata $bundleCand
            if ($meta) {
                $v = Parse-VersionTuple $meta.Version
                if ($v -gt $bestVer) {
                    $bestVer = $v
                    $best = [PSCustomObject]@{
                        Kind    = "bundle"
                        Path    = $bundleCand
                        Version = $meta.Version
                        TagDir  = $dir.FullName
                        Label   = "已下载更新 v$($meta.Version) ($($dir.Name))"
                    }
                }
            }
        }
    }
    return $best
}

function Test-MaxAppInstalled {
    param([int]$Year)
    # 1. Check user profile directory (%LOCALAPPDATA%\Autodesk\3dsMax\<year> - 64bit)
    $localDir = Join-Path $env:LOCALAPPDATA "Autodesk\3dsMax\$Year - 64bit"
    if (Test-Path $localDir) { return $true }

    # 2. Check HKLM registry keys (2026 -> 28.0, 2027 -> 29.0)
    $majorNum = $Year - 1998
    $regPaths = @(
        "HKLM:\SOFTWARE\Autodesk\3dsMax\$majorNum.0",
        "HKLM:\SOFTWARE\Autodesk\3dsMax\$Year"
    )
    foreach ($rp in $regPaths) {
        if (Test-Path $rp) { return $true }
    }
    return $false
}

function Get-AllSearchPluginRoots {
    $roots = @($script:PrimaryPluginsRoot)
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        $progDataRoot = Join-Path $env:ProgramData "Autodesk\ApplicationPlugins"
        if (($roots -notcontains $progDataRoot) -and (Test-Path $progDataRoot)) {
            $roots += $progDataRoot
        }
    }
    return $roots
}

function Get-InstalledStatusForYear {
    param([int]$Year)
    $roots = Get-AllSearchPluginRoots
    foreach ($root in $roots) {
        $verBundle = Join-Path $root "MaxHotbox_$Year.bundle"
        if (Test-Path $verBundle) {
            $meta = Get-BundleMetadata $verBundle
            return [PSCustomObject]@{
                Year       = $Year
                Installed  = $true
                Version    = if ($meta) { $meta.Version } else { "未知" }
                BundlePath = $verBundle
                IsLegacy   = $false
                ScopeRoot  = $root
            }
        }
    }
    foreach ($root in $roots) {
        $legacyBundle = Join-Path $root "MaxHotbox.bundle"
        if (Test-Path $legacyBundle) {
            $meta = Get-BundleMetadata $legacyBundle
            if ($meta -and $Year -ge $meta.SeriesMin -and $Year -le $meta.SeriesMax) {
                return [PSCustomObject]@{
                    Year       = $Year
                    Installed  = $true
                    Version    = $meta.Version
                    BundlePath = $legacyBundle
                    IsLegacy   = $true
                    ScopeRoot  = $root
                }
            }
        }
    }
    return [PSCustomObject]@{
        Year       = $Year
        Installed  = $false
        Version    = ""
        BundlePath = ""
        IsLegacy   = $false
        ScopeRoot  = $script:PrimaryPluginsRoot
    }
}

function Patch-BundleXmlForYear {
    param([string]$BundlePath, [int]$Year)
    $xmlPath = Join-Path $BundlePath "PackageContents.xml"
    [xml]$doc = Get-Content -Path $xmlPath -Raw -Encoding UTF8
    $pkg = $doc.ApplicationPackage
    $pkg.SetAttribute("ProductCode", "{9D4C8A12-$Year-4B7E-9A51-5E8C3A4F1000}")
    $pkg.SetAttribute("Description", "Maya-style multi-level radial marking menu and 5-zone hotbox plugin for Autodesk 3ds Max $Year.")
    foreach ($req in $doc.SelectNodes("//RuntimeRequirements")) {
        $req.SetAttribute("SeriesMin", [string]$Year)
        $req.SetAttribute("SeriesMax", [string]$Year)
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $sw = New-Object System.IO.StreamWriter($xmlPath, $false, $utf8NoBom)
    try {
        $doc.Save($sw)
    } finally {
        $sw.Dispose()
    }
}

function Migrate-LegacyBundleExcludingYear {
    param([string]$PluginsRoot, [int]$ExcludedYear)
    $legacyPath = Join-Path $PluginsRoot "MaxHotbox.bundle"
    if (-not (Test-Path $legacyPath)) { return }
    $meta = Get-BundleMetadata $legacyPath
    if ($null -eq $meta) { return }
    if ($ExcludedYear -lt $meta.SeriesMin -or $ExcludedYear -gt $meta.SeriesMax) { return }

    # Preserve any OTHER supported year that the legacy bundle also covered
    foreach ($otherYear in $script:SupportedYears) {
        if ($otherYear -eq $ExcludedYear) { continue }
        if ($otherYear -ge $meta.SeriesMin -and $otherYear -le $meta.SeriesMax) {
            $otherBundle = Join-Path $PluginsRoot "MaxHotbox_$otherYear.bundle"
            if (-not (Test-Path $otherBundle)) {
                Copy-Item -Path $legacyPath -Destination $otherBundle -Recurse -Force
                Patch-BundleXmlForYear -BundlePath $otherBundle -Year $otherYear
                Write-Host "[INFO] 已将旧版通用包中 3ds Max $otherYear 部分平滑迁移至: $otherBundle" -ForegroundColor DarkCyan
            }
        }
    }

    Remove-Item -Path $legacyPath -Recurse -Force
    Write-Host "[INFO] 已清理旧版冲突包: $legacyPath" -ForegroundColor DarkGray
}

function Install-MaxHotboxForYear {
    param(
        [int]$Year,
        [PSCustomObject]$Source
    )
    if ($null -eq $Source) {
        throw "未找到可用的 MaxHotbox.bundle 或源码目录。"
    }
    if (-not (Test-Path $script:PrimaryPluginsRoot)) {
        New-Item -ItemType Directory -Path $script:PrimaryPluginsRoot -Force | Out-Null
    }

    # Prevent duplicate loading if a legacy MaxHotbox.bundle covered this year
    Migrate-LegacyBundleExcludingYear -PluginsRoot $script:PrimaryPluginsRoot -ExcludedYear $Year

    $targetBundle = Join-Path $script:PrimaryPluginsRoot "MaxHotbox_$Year.bundle"
    if (Test-Path $targetBundle) {
        Remove-Item -Path $targetBundle -Recurse -Force
    }

    if ($Source.Kind -eq "bundle") {
        Copy-Item -Path $Source.Path -Destination $targetBundle -Recurse -Force
    } elseif ($Source.Kind -eq "repo") {
        $contents = Join-Path $targetBundle "Contents"
        New-Item -ItemType Directory -Path (Join-Path $contents "macroscripts") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $contents "scripts") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $contents "python") -Force | Out-Null

        Copy-Item (Join-Path $Source.Path "packaging\PackageContents.xml") (Join-Path $targetBundle "PackageContents.xml") -Force
        Copy-WithUtf8Bom (Join-Path $Source.Path "src\maxscript\MaxHotbox.mcr") (Join-Path $contents "macroscripts\MaxHotbox.mcr")
        Copy-WithUtf8Bom (Join-Path $Source.Path "src\maxscript\post_startup.ms") (Join-Path $contents "scripts\post_startup.ms")
        Copy-WithUtf8Bom (Join-Path $Source.Path "src\maxscript\uninstall_helper.ms") (Join-Path $contents "scripts\uninstall_helper.ms")
        Copy-Item (Join-Path $Source.Path "src\max_hotbox") (Join-Path $contents "python\max_hotbox") -Recurse -Force
        Get-ChildItem -Path (Join-Path $contents "python\max_hotbox") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    } else {
        throw "不支持的安装源类型: $($Source.Kind)"
    }

    # Scope PackageContents.xml strictly to this Max version so 2026 & 2027 are 100% independent
    Patch-BundleXmlForYear -BundlePath $targetBundle -Year $Year

    # Verify critical files
    $required = @(
        (Join-Path $targetBundle "PackageContents.xml"),
        (Join-Path $targetBundle "Contents\macroscripts\MaxHotbox.mcr"),
        (Join-Path $targetBundle "Contents\scripts\post_startup.ms"),
        (Join-Path $targetBundle "Contents\python\max_hotbox\controller.py"),
        (Join-Path $targetBundle "Contents\python\max_hotbox\graphite_tools.py")
    )
    foreach ($req in $required) {
        if (-not (Test-Path $req)) {
            throw "安装校验失败 (3ds Max $Year)，缺少文件: $req"
        }
    }

    $meta = Get-BundleMetadata $targetBundle
    $verStr = if ($meta) { $meta.Version } else { Get-SourceVersion $Source }
    Write-Host " [OK] 3ds Max $Year 已安装 MaxHotbox v$verStr -> $targetBundle" -ForegroundColor Green
}

function Uninstall-MaxHotboxForYear {
    param(
        [int]$Year,
        [bool]$CleanUserConfig = $false
    )
    $roots = Get-AllSearchPluginRoots
    $removed = $false

    foreach ($root in $roots) {
        $verBundle = Join-Path $root "MaxHotbox_$Year.bundle"
        if (Test-Path $verBundle) {
            Remove-Item -Path $verBundle -Recurse -Force
            Write-Host " [OK] 已卸载 3ds Max $Year 插件包: $verBundle" -ForegroundColor Green
            $removed = $true
        }

        $legacyPath = Join-Path $root "MaxHotbox.bundle"
        if (Test-Path $legacyPath) {
            $meta = Get-BundleMetadata $legacyPath
            if ($meta -and $Year -ge $meta.SeriesMin -and $Year -le $meta.SeriesMax) {
                Migrate-LegacyBundleExcludingYear -PluginsRoot $root -ExcludedYear $Year
                Write-Host " [OK] 已从旧版通用插件包移除 3ds Max $Year 支持。" -ForegroundColor Green
                $removed = $true
            }
        }
    }

    if (-not $removed) {
        Write-Host " [INFO] 3ds Max $Year 当前未安装 MaxHotbox。" -ForegroundColor Yellow
    }

    if ($CleanUserConfig) {
        $maxUserBase = Join-Path $env:LOCALAPPDATA "Autodesk\3dsMax\$Year - 64bit"
        if (Test-Path $maxUserBase) {
            foreach ($langDir in (Get-ChildItem -Path $maxUserBase -Directory -ErrorAction SilentlyContinue)) {
                $cfgDir = Join-Path $langDir.FullName "userconfig\MaxHotbox"
                if (Test-Path $cfgDir) {
                    Remove-Item -Path $cfgDir -Recurse -Force
                    Write-Host " [OK] 已清理 3ds Max $Year 用户配置: $cfgDir" -ForegroundColor Green
                }
            }
        }
    }
}

function Get-LatestGitHubRelease {
    $apiUrl = "https://api.github.com/repos/$($script:GitHubRepo)/releases?per_page=10"
    $headers = @{
        "User-Agent"           = "MaxHotbox-Manager"
        "Accept"               = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
    }
    $tok = if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { $env:GITHUB_TOKEN } elseif (-not [string]::IsNullOrWhiteSpace($env:GH_TOKEN)) { $env:GH_TOKEN } else { "" }
    if (-not [string]::IsNullOrWhiteSpace($tok)) {
        $headers["Authorization"] = "Bearer $tok"
    }

    Write-Host "[INFO] 正在连接 GitHub 查询最新版本 ($($script:GitHubRepo))..." -ForegroundColor Cyan
    try {
        $releases = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Get -TimeoutSec 15
        if ($null -ne $releases) {
            $list = @($releases) | Where-Object { -not $_.draft }
            if ($list.Count -gt 0) {
                return $list[0]
            }
        }
    } catch {
        Write-Host "[INFO] GitHub API 触发限流或不可用，自动切换为 GitHub Releases 公开通道..." -ForegroundColor DarkYellow
    }

    # Rate-limit-free fallback: GitHub public Releases Atom feed + expanded_assets HTML
    $webHeaders = @{ "User-Agent" = "MaxHotbox-Manager" }
    $atomResp = Invoke-WebRequest -Uri "https://github.com/$($script:GitHubRepo)/releases.atom" -Headers $webHeaders -UseBasicParsing -TimeoutSec 20
    [xml]$atomXml = $atomResp.Content
    $entry = $atomXml.feed.entry | Select-Object -First 1
    if ($null -eq $entry) {
        throw "未在 GitHub 找到任何已发布的 Release。"
    }
    $href = [string]$entry.link.href
    $tag = ($href.TrimEnd('/') -split '/')[-1]
    $title = [string]$entry.title
    $updated = [string]$entry.updated

    $assetsResp = Invoke-WebRequest -Uri "https://github.com/$($script:GitHubRepo)/releases/expanded_assets/$tag" -Headers $webHeaders -UseBasicParsing -TimeoutSec 20
    $matches = [regex]::Matches($assetsResp.Content, 'href="(/[^"]+/releases/download/[^"]+)"')
    $assets = @()
    $seen = @{}
    foreach ($m in $matches) {
        $relPath = $m.Groups[1].Value
        if ($seen.ContainsKey($relPath)) { continue }
        $seen[$relPath] = $true
        $fileName = [System.Uri]::UnescapeDataString(($relPath -split '/')[-1])
        $assets += [PSCustomObject]@{
            name                 = $fileName
            browser_download_url = "https://github.com$relPath"
            size                 = 0
        }
    }

    return [PSCustomObject]@{
        tag_name     = $tag
        name         = $title
        published_at = $updated
        assets       = $assets
    }
}

function Verify-DownloadedChecksums {
    param([string]$TargetDir, [string]$ShaFile)
    if (-not (Test-Path $ShaFile)) { return $true }
    $lines = Get-Content -Path $ShaFile -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $allOk = $true
    foreach ($line in $lines) {
        if ($line -match '^([0-9a-fA-F]{64})\s+(.+)$') {
            $expected = $Matches[1].ToLowerInvariant()
            $fileName = $Matches[2].Trim()
            $filePath = Join-Path $TargetDir $fileName
            if (Test-Path $filePath) {
                $actual = (Get-FileHash -Path $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actual -eq $expected) {
                    Write-Host " [OK] SHA-256 校验通过: $fileName" -ForegroundColor Green
                } else {
                    Write-Host " [ERROR] SHA-256 校验失败: $fileName" -ForegroundColor Red
                    $allOk = $false
                }
            }
        }
    }
    return $allOk
}

function Download-GitHubReleaseAssets {
    param([object]$Release)
    $tag = [string]$Release.tag_name
    $destDir = Join-Path $script:DownloadsRoot $tag
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    $assets = @($Release.assets)
    if ($assets.Count -eq 0) {
        throw "Release $tag 未包含可下载的附件。"
    }

    $zipPath = ""
    $shaPath = ""
    $headers = @{ "User-Agent" = "MaxHotbox-Manager" }

    foreach ($asset in $assets) {
        $name = [string]$asset.name
        $url = [string]$asset.browser_download_url
        $outFile = Join-Path $destDir $name
        $sizeHint = if ($asset.size -gt 0) { " ($([math]::Round($asset.size / 1024.0, 1)) KB)" } else { "" }
        Write-Host "[INFO] 正在下载: $name$sizeHint..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $url -OutFile $outFile -Headers $headers -UseBasicParsing -TimeoutSec 60
        if ($name -like "*.zip") { $zipPath = $outFile }
        if ($name -like "*SHA256*.txt") { $shaPath = $outFile }
    }

    if (-not [string]::IsNullOrWhiteSpace($shaPath)) {
        $ok = Verify-DownloadedChecksums -TargetDir $destDir -ShaFile $shaPath
        if (-not $ok) {
            throw "下载文件校验失败，请检查网络后重试。"
        }
    }

    $extractedDir = Join-Path $destDir "extracted"
    if (-not [string]::IsNullOrWhiteSpace($zipPath) -and (Test-Path $zipPath)) {
        if (Test-Path $extractedDir) {
            Remove-Item -Path $extractedDir -Recurse -Force
        }
        Write-Host "[INFO] 正在解压更新包到: $extractedDir" -ForegroundColor Cyan
        Expand-Archive -Path $zipPath -DestinationPath $extractedDir -Force
    }

    Write-Host " [OK] 最新版本 $tag 已下载并就绪: $destDir" -ForegroundColor Green
    return [PSCustomObject]@{
        Tag          = $tag
        DownloadDir  = $destDir
        ZipPath      = $zipPath
        ExtractedDir = $extractedDir
        BundlePath   = (Join-Path $extractedDir "MaxHotbox.bundle")
    }
}

function Parse-TargetYears {
    param([string]$Spec)
    if ([string]::IsNullOrWhiteSpace($Spec) -or $Spec -ieq "All") {
        return @($script:SupportedYears)
    }
    $years = @()
    foreach ($tok in ($Spec -split '[,\s;]+')) {
        if ($tok -match '^\d{4}$') {
            $y = [int]$tok
            if ($script:SupportedYears -contains $y) {
                $years += $y
            } else {
                throw "不支持的 3ds Max 版本: $y (支持: $($script:SupportedYears -join ', '))"
            }
        }
    }
    if ($years.Count -eq 0) {
        throw "无法解析目标版本参数: $Spec"
    }
    return @($years | Select-Object -Unique)
}

function Show-StatusBanner {
    param([switch]$Detailed)
    $localSrc = Resolve-InstallSource -OverrideDir $SourceDir
    $localVer = Get-SourceVersion $localSrc
    $dlSrc = Find-LatestDownloadedSource

    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "   MaxHotbox 多版本插件管理器 (Autodesk 3ds Max 2026 / 2027)" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ("  本地包版本 : v{0}" -f $localVer) -ForegroundColor White
    if ($dlSrc) {
        Write-Host ("  已下载更新 : v{0} ({1})" -f $dlSrc.Version, $dlSrc.TagDir) -ForegroundColor Yellow
    }
    Write-Host ("  GitHub仓库 : https://github.com/{0}" -f $script:GitHubRepo) -ForegroundColor DarkGray
    Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  [各版本 3ds Max 安装状态]" -ForegroundColor White

    foreach ($year in $script:SupportedYears) {
        $appFound = Test-MaxAppInstalled $year
        $st = Get-InstalledStatusForYear $year
        $appTag = if ($appFound) { "已检测到Max" } else { "未检测到Max" }
        if ($st.Installed) {
            $legacyNote = if ($st.IsLegacy) { " [旧版通用包]" } else { "" }
            Write-Host ("    - 3ds Max {0} ({1}) : 已安装 v{2}{3}" -f $year, $appTag, $st.Version, $legacyNote) -ForegroundColor Green
            if ($Detailed) {
                Write-Host ("        路径: {0}" -f $st.BundlePath) -ForegroundColor DarkGray
            }
        } else {
            Write-Host ("    - 3ds Max {0} ({1}) : 未安装" -f $year, $appTag) -ForegroundColor DarkYellow
        }
    }
    if ($Detailed) {
        Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
        Write-Host ("  插件安装根目录 : {0}" -f $script:PrimaryPluginsRoot) -ForegroundColor DarkGray
        Write-Host ("  更新包下载目录 : {0}" -f $script:DownloadsRoot) -ForegroundColor DarkGray
        if ($localSrc) {
            Write-Host ("  当前安装源     : {0}" -f $localSrc.Label) -ForegroundColor DarkGray
        }
    }
    Write-Host "================================================================" -ForegroundColor Cyan
}

function Show-PostInstallHint {
    $maxRunning = [bool](Get-Process -Name "3dsmax" -ErrorAction SilentlyContinue)
    if ($maxRunning) {
        Write-Host "[提示] 检测到 3ds Max 正在运行:" -ForegroundColor Yellow
        Write-Host "  - 免重启生效: 在 Max 顶部 [脚本 -> 运行脚本...] 选择 Load_MaxHotbox_Now.ms 立即热重载"
        Write-Host "  - 或重启 3ds Max 自动加载新版本。"
    } else {
        Write-Host "[提示] 启动对应的 3ds Max 后，顶部菜单栏将自动出现 [MaxHotbox] 按钮。" -ForegroundColor Yellow
    }
}

function Invoke-UpdateInstalledWorkflow {
    param(
        [int[]]$ExplicitYears = @(),
        [bool]$Online = $false,
        [bool]$Interactive = $false
    )

    $installedStates = @()
    foreach ($y in $script:SupportedYears) {
        $st = Get-InstalledStatusForYear $y
        if ($st.Installed) { $installedStates += $st }
    }

    if ($installedStates.Count -eq 0) {
        Write-Host "[提示] 当前未检测到任何已安装的 MaxHotbox（2026 / 2027）。请先使用菜单 [1]/[2]/[3] 安装插件。" -ForegroundColor Yellow
        return
    }

    $chosenYears = @()
    if ($ExplicitYears.Count -gt 0) {
        foreach ($y in $ExplicitYears) {
            if (($installedStates | Where-Object { $_.Year -eq $y }).Count -gt 0) {
                $chosenYears += $y
            } else {
                Write-Host "[跳过] 3ds Max $y 当前未安装 MaxHotbox，已跳过更新。" -ForegroundColor Yellow
            }
        }
    } elseif ($Interactive) {
        Write-Host ""
        Write-Host "当前已安装插件的版本:" -ForegroundColor Cyan
        foreach ($st in $installedStates) {
            Write-Host ("  - 3ds Max {0} : v{1}" -f $st.Year, $st.Version) -ForegroundColor Green
        }
        Write-Host ""
        Write-Host "请选择要更新的版本:" -ForegroundColor White
        Write-Host "  [1] 更新全部已安装版本 ($((($installedStates | ForEach-Object { $_.Year }) -join ' + ')))"
        $idxMap = @{}
        $idx = 2
        foreach ($st in $installedStates) {
            Write-Host ("  [{0}] 仅更新 3ds Max {1} (当前 v{2})" -f $idx, $st.Year, $st.Version)
            $idxMap[[string]$idx] = @($st.Year)
            $idx++
        }
        Write-Host "  [0] 返回主菜单"
        $sel = (Read-Host "请输入数字").Trim()
        if ($sel -eq "0" -or [string]::IsNullOrWhiteSpace($sel)) { return }
        if ($sel -eq "1") {
            $chosenYears = @($installedStates | ForEach-Object { $_.Year })
        } elseif ($idxMap.ContainsKey($sel)) {
            $chosenYears = $idxMap[$sel]
        } else {
            Write-Host "[提示] 无效输入，已取消。" -ForegroundColor Yellow
            return
        }

        Write-Host ""
        Write-Host "请选择更新来源:" -ForegroundColor White
        Write-Host "  [1] 从 GitHub 检查并下载最新版本后更新 (在线更新)"
        Write-Host "  [2] 使用本地当前包 / 已下载的本地最新更新包 (离线更新)"
        $srcSel = (Read-Host "请输入数字 [默认 1]").Trim()
        if ($srcSel -eq "2") {
            $Online = $false
        } else {
            $Online = $true
        }
    } else {
        $chosenYears = @($installedStates | ForEach-Object { $_.Year })
    }

    if ($chosenYears.Count -eq 0) { return }

    $updateSource = $null
    if ($Online) {
        $rel = Get-LatestGitHubRelease
        $dl = Download-GitHubReleaseAssets -Release $rel
        if (Test-Path (Join-Path $dl.BundlePath "PackageContents.xml")) {
            $updateSource = [PSCustomObject]@{
                Kind  = "bundle"
                Path  = $dl.BundlePath
                Label = "GitHub 最新版 $($dl.Tag)"
            }
        } else {
            throw "已下载并解压的更新包中未找到 MaxHotbox.bundle。"
        }
    } else {
        $localSrc = Resolve-InstallSource -OverrideDir $SourceDir
        $dlSrc = Find-LatestDownloadedSource
        if ($dlSrc -and $localSrc) {
            $localVer = Get-SourceVersion $localSrc
            if ((Compare-PluginVersion $dlSrc.Version $localVer) -gt 0) {
                $updateSource = $dlSrc
            } else {
                $updateSource = $localSrc
            }
        } elseif ($dlSrc) {
            $updateSource = $dlSrc
        } else {
            $updateSource = $localSrc
        }
    }

    if ($null -eq $updateSource) {
        throw "未找到可用于更新的本地插件包。"
    }

    $newVer = Get-SourceVersion $updateSource
    Write-Host ""
    Write-Host "[INFO] 使用更新源: $($updateSource.Label) (v$newVer)" -ForegroundColor Cyan

    foreach ($y in $chosenYears) {
        $oldState = $installedStates | Where-Object { $_.Year -eq $y } | Select-Object -First 1
        $oldVer = if ($oldState) { $oldState.Version } else { "未知" }
        Install-MaxHotboxForYear -Year $y -Source $updateSource
        Write-Host ("      版本变更: 3ds Max {0}  v{1} -> v{2} (个人配置已完整保留)" -f $y, $oldVer, $newVer) -ForegroundColor Cyan
    }
    Show-PostInstallHint
}

function Invoke-CheckAndDownloadInteractive {
    $rel = Get-LatestGitHubRelease
    $remoteTag = [string]$rel.tag_name
    $remoteVer = ($remoteTag -replace '^[vV]', '')
    $localSrc = Resolve-InstallSource -OverrideDir $SourceDir
    $localVer = Get-SourceVersion $localSrc

    Write-Host ""
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host ("  GitHub 最新版本 : {0} ({1})" -f $remoteTag, $rel.name) -ForegroundColor Green
    Write-Host ("  发布时间 (UTC)  : {0}" -f $rel.published_at) -ForegroundColor DarkGray
    Write-Host ("  当前本地版本    : v{0}" -f $localVer) -ForegroundColor White
    $cmp = Compare-PluginVersion $remoteVer $localVer
    if ($cmp -gt 0) {
        Write-Host "  状态            : 发现新版本可下载！" -ForegroundColor Yellow
    } elseif ($cmp -eq 0) {
        Write-Host "  状态            : 本地已是最新版本。" -ForegroundColor Green
    } else {
        Write-Host "  状态            : 本地开发版本高于 GitHub 已发布版本。" -ForegroundColor Cyan
    }
    Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan

    $ans = (Read-Host "是否将 GitHub 最新版本 $remoteTag 下载到本地 downloads 目录? [Y/n]").Trim()
    if ($ans -match '^[Nn]') {
        Write-Host "[INFO] 已取消下载。" -ForegroundColor Yellow
        return
    }

    $dl = Download-GitHubReleaseAssets -Release $rel

    # Offer immediate update if any Max version already has MaxHotbox installed
    $installedYears = @()
    foreach ($y in $script:SupportedYears) {
        if ((Get-InstalledStatusForYear $y).Installed) { $installedYears += $y }
    }
    if ($installedYears.Count -gt 0 -and (Test-Path (Join-Path $dl.BundlePath "PackageContents.xml"))) {
        $applyAns = (Read-Host ("是否立即将已下载的 {0} 更新到已安装版本 ({1})? [Y/n]" -f $remoteTag, ($installedYears -join " + "))).Trim()
        if ($applyAns -notmatch '^[Nn]') {
            $dlSource = [PSCustomObject]@{
                Kind  = "bundle"
                Path  = $dl.BundlePath
                Label = "GitHub 最新版 $remoteTag"
            }
            foreach ($y in $installedYears) {
                Install-MaxHotboxForYear -Year $y -Source $dlSource
            }
            Show-PostInstallHint
        }
    }
}

function Invoke-InteractiveMenu {
    while ($true) {
        Show-StatusBanner
        Write-Host ""
        Write-Host "  [1] 安装插件 -> 3ds Max 2026" -ForegroundColor White
        Write-Host "  [2] 安装插件 -> 3ds Max 2027" -ForegroundColor White
        Write-Host "  [3] 安装插件 -> 全部支持版本 (3ds Max 2026 + 2027)" -ForegroundColor White
        Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkGray
        Write-Host "  [4] 卸载插件 -> 3ds Max 2026" -ForegroundColor White
        Write-Host "  [5] 卸载插件 -> 3ds Max 2027" -ForegroundColor White
        Write-Host "  [6] 卸载插件 -> 全部版本 (3ds Max 2026 + 2027)" -ForegroundColor White
        Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkGray
        Write-Host "  [7] 检查插件更新 (查询 GitHub 最新版本并下载到本地)" -ForegroundColor Cyan
        Write-Host "  [8] 更新已安装到不同版本的插件 (按版本选择或一键更新)" -ForegroundColor Cyan
        Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkGray
        Write-Host "  [9] 刷新并查看详细路径信息" -ForegroundColor DarkGray
        Write-Host "  [0] 退出" -ForegroundColor DarkGray
        Write-Host ""

        $choice = (Read-Host "请输入功能编号 (0-9)").Trim()
        Write-Host ""

        try {
            switch ($choice) {
                "1" {
                    $src = Resolve-InstallSource -OverrideDir $SourceDir
                    Install-MaxHotboxForYear -Year 2026 -Source $src
                    Show-PostInstallHint
                }
                "2" {
                    $src = Resolve-InstallSource -OverrideDir $SourceDir
                    Install-MaxHotboxForYear -Year 2027 -Source $src
                    Show-PostInstallHint
                }
                "3" {
                    $src = Resolve-InstallSource -OverrideDir $SourceDir
                    foreach ($y in $script:SupportedYears) {
                        Install-MaxHotboxForYear -Year $y -Source $src
                    }
                    Show-PostInstallHint
                }
                "4" {
                    $clean = (Read-Host "是否同时清理 3ds Max 2026 的个人配置与日志? [y/N]").Trim() -match '^[Yy]'
                    Uninstall-MaxHotboxForYear -Year 2026 -CleanUserConfig:$clean
                }
                "5" {
                    $clean = (Read-Host "是否同时清理 3ds Max 2027 的个人配置与日志? [y/N]").Trim() -match '^[Yy]'
                    Uninstall-MaxHotboxForYear -Year 2027 -CleanUserConfig:$clean
                }
                "6" {
                    $clean = (Read-Host "是否同时清理所有版本的个人配置与日志? [y/N]").Trim() -match '^[Yy]'
                    foreach ($y in $script:SupportedYears) {
                        Uninstall-MaxHotboxForYear -Year $y -CleanUserConfig:$clean
                    }
                }
                "7" {
                    Invoke-CheckAndDownloadInteractive
                }
                "8" {
                    Invoke-UpdateInstalledWorkflow -Interactive:$true
                }
                "9" {
                    Show-StatusBanner -Detailed
                }
                "0" {
                    Write-Host "已退出 MaxHotbox 插件管理器。" -ForegroundColor DarkGray
                    return
                }
                default {
                    Write-Host "[提示] 请输入有效的数字编号 (0-9)。" -ForegroundColor Yellow
                }
            }
        } catch {
            Write-Host "[ERROR] 操作失败: $($_.Exception.Message)" -ForegroundColor Red
        }

        Write-Host ""
        if (-not $NoPause) {
            Read-Host "按回车键返回主菜单" | Out-Null
        }
    }
}

# ------------------------------------------------------------------ Entrypoint
try {
    switch ($Action) {
        "Menu" {
            Invoke-InteractiveMenu
        }
        "Status" {
            Show-StatusBanner -Detailed
        }
        "Install" {
            $years = Parse-TargetYears $TargetVersions
            $src = Resolve-InstallSource -OverrideDir $SourceDir
            foreach ($y in $years) {
                Install-MaxHotboxForYear -Year $y -Source $src
            }
            Show-PostInstallHint
        }
        "Uninstall" {
            $years = Parse-TargetYears $TargetVersions
            foreach ($y in $years) {
                Uninstall-MaxHotboxForYear -Year $y -CleanUserConfig:([bool]$RemoveUserConfig)
            }
        }
        "CheckUpdate" {
            $rel = Get-LatestGitHubRelease
            $remoteTag = [string]$rel.tag_name
            $remoteVer = ($remoteTag -replace '^[vV]', '')
            $localSrc = Resolve-InstallSource -OverrideDir $SourceDir
            $localVer = Get-SourceVersion $localSrc
            $cmp = Compare-PluginVersion $remoteVer $localVer
            Write-Host ("GitHub 最新版本 : {0} (发布于 {1})" -f $remoteTag, $rel.published_at) -ForegroundColor Green
            Write-Host ("本地当前版本    : v{0}" -f $localVer) -ForegroundColor White
            if ($cmp -gt 0) {
                Write-Host "检查结果        : 有新版本可用" -ForegroundColor Yellow
            } elseif ($cmp -eq 0) {
                Write-Host "检查结果        : 已是最新版本" -ForegroundColor Green
            } else {
                Write-Host "检查结果        : 本地版本高于线上版本" -ForegroundColor Cyan
            }
        }
        "DownloadUpdate" {
            $rel = Get-LatestGitHubRelease
            Download-GitHubReleaseAssets -Release $rel | Out-Null
        }
        "UpdateInstalled" {
            $years = if ([string]::IsNullOrWhiteSpace($TargetVersions)) { @() } else { Parse-TargetYears $TargetVersions }
            Invoke-UpdateInstalledWorkflow -ExplicitYears $years -Online:([bool]$UseOnlineUpdate) -Interactive:$false
        }
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "按回车键退出" | Out-Null }
    exit 1
}
