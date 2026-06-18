param(
    [string]$ScriptsDir = "",
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

function Add-Dir {
    param([System.Collections.Generic.List[string]]$List, [string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    try {
        $resolved = (Get-Item -LiteralPath $Path -ErrorAction Stop).FullName
        if (-not $List.Contains($resolved)) {
            $List.Add($resolved) | Out-Null
        }
    } catch {
    }
}

function Find-IllustratorScriptDirs {
    $roots = [System.Collections.Generic.List[string]]::new()

    Get-Process Illustrator -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Path) {
            $dir = Split-Path -Parent $_.Path
            while ($dir -and -not (Test-Path -LiteralPath (Join-Path $dir "Presets"))) {
                $parent = Split-Path -Parent $dir
                if ($parent -eq $dir) { break }
                $dir = $parent
            }
            if ($dir -and (Test-Path -LiteralPath (Join-Path $dir "Presets"))) {
                Add-Dir $roots $dir
            }
        }
    }

    @(
        "E:\Adode\Adobe Illustrator 2021",
        "C:\Program Files\Adobe\Adobe Illustrator 2021",
        "C:\Program Files\Adobe",
        "C:\Program Files",
        "C:\Program Files (x86)"
    ) | ForEach-Object {
        if (Test-Path -LiteralPath $_) {
            if ($_ -match "Adobe Illustrator") {
                Add-Dir $roots $_
            } else {
                Get-ChildItem -LiteralPath $_ -Directory -Filter "Adobe Illustrator*" -ErrorAction SilentlyContinue |
                    ForEach-Object { Add-Dir $roots $_.FullName }
            }
        }
    }

    $scriptDirs = [System.Collections.Generic.List[string]]::new()
    foreach ($root in $roots) {
        foreach ($localeDir in Get-ChildItem -LiteralPath (Join-Path $root "Presets") -Directory -ErrorAction SilentlyContinue) {
            Add-Dir $scriptDirs (Join-Path $localeDir.FullName "Scripts")
            Add-Dir $scriptDirs (Join-Path $localeDir.FullName "scripts")
            Add-Dir $scriptDirs (Join-Path $localeDir.FullName "脚本")
        }
    }

    return $scriptDirs
}

$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptNames = @(
    "MergeText_AI.jsx",
    "MergeText_AI_Quick.jsx",
    "ReleaseClippingMask.jsx"
)

foreach ($name in $scriptNames) {
    $file = Join-Path $sourceDir $name
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Missing required file: $file"
    }
}

if ($ScriptsDir) {
    $targets = @((Get-Item -LiteralPath $ScriptsDir -ErrorAction Stop).FullName)
} else {
    $targets = @(Find-IllustratorScriptDirs)
}

if (-not $targets -or $targets.Count -eq 0) {
    throw "No Illustrator Scripts folder was found. Pass -ScriptsDir `"E:\...\Presets\zh_CN\脚本`"."
}

Write-Host "Illustrator Scripts folder(s):"
$targets | ForEach-Object { Write-Host "  $_" }

if ($ListOnly) {
    Write-Host "ListOnly: no files copied."
    exit 0
}

foreach ($target in $targets) {
    foreach ($name in $scriptNames) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $name) -Destination (Join-Path $target $name) -Force
    }
    Write-Host "Installed:"
    foreach ($name in $scriptNames) {
        Write-Host "  $(Join-Path $target $name)"
    }
}

Write-Host ""
Write-Host "Restart Illustrator, then use File > Scripts > MergeText_AI, MergeText_AI_Quick, or ReleaseClippingMask."
