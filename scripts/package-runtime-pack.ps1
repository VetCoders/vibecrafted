#Requires -Version 5.1
<#
.SYNOPSIS
    Package a Windows Runtime Pack payload directory into the canonical tar.gz carrier.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PayloadRoot,
    [Parameter(Mandatory = $true)][string]$Output,
    [Parameter(Mandatory = $true)][string]$SourceRevision,
    [Parameter(Mandatory = $true)][string]$TerminalRevision,
    [Parameter(Mandatory = $true)][string]$FrameRevision,
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Platform = "win32",
    [string]$Architecture = "x64"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Die([string]$Message) { Write-Error "Runtime Pack packaging failed: $Message"; exit 1 }

$payload = (Resolve-Path -LiteralPath $PayloadRoot).Path
$required = @(
    "VERSION",
    "bin\python.exe",
    "bin\vibecrafted.cmd",
    "scripts\vetcoders_install.py",
    "scripts\install-runtime-pack.ps1",
    "vibecrafted-core\vibecrafted_core\runtime_pack_contract.py"
)
foreach ($relative in $required) {
    $path = Join-Path $payload $relative
    if (-not (Test-Path -LiteralPath $path)) {
        Die "standalone Runtime Pack is missing $relative"
    }
}

$links = Get-ChildItem -LiteralPath $payload -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
if ($links) {
    Die "standalone Runtime Pack contains reparse points/symlinks"
}

$python = Join-Path $payload "bin\python.exe"
$env:PYTHONPATH = Join-Path $payload "vibecrafted-core"
$env:PYTHONNOUSERSITE = "1"
& $python -m vibecrafted_core.runtime_pack_contract write `
    --root $payload `
    --carrier-basename ([IO.Path]::GetFileName($Output)) `
    --version $Version `
    --platform $Platform `
    --architecture $Architecture `
    --source-revision $SourceRevision `
    --terminal-revision $TerminalRevision `
    --frame-revision $FrameRevision
if ($LASTEXITCODE -ne 0) { Die "provenance write failed" }

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vibecrafted-runtime-pack-build-" + [guid]::NewGuid().ToString("N"))
$root = Join-Path $work "VibecraftedRuntime"
New-Item -ItemType Directory -Path $root | Out-Null
Copy-Item -LiteralPath (Join-Path $payload "*") -Destination $root -Recurse -Force
$outDir = Split-Path -Parent $Output
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}
Push-Location $work
try {
    & tar -czf $Output VibecraftedRuntime
    if ($LASTEXITCODE -ne 0) { Die "tar failed" }
}
finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
$hash = ([BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.IO.File]::ReadAllBytes($Output))) -replace '-', '').ToLowerInvariant()
$checksum = "$Output.sha256"
Set-Content -LiteralPath $checksum -Value "$hash  $([IO.Path]::GetFileName($Output))" -Encoding ascii
Write-Output $Output
