#Requires -Version 5.1
<#
.SYNOPSIS
    Verify and install one Vibecrafted Runtime Pack on native Windows.

.DESCRIPTION
    Same receipted installer as macOS/Linux: checksum + signature before extract,
    pack-owned Python runs scripts/vetcoders_install.py runtime-install.
    Does not require WSL, Homebrew, or a developer toolchain.
#>
[CmdletBinding()]
param(
    [string]$Pack = $env:VIBECRAFTED_RUNTIME_PACK,
    [switch]$Uninstall,
    [switch]$VerifyOnly,
    [switch]$DryRun,
    [string]$ExpectedSourceRevision = "",
    [string]$ExpectedTerminalRevision = "",
    [string]$ExpectedFrameRevision = "",
    [string]$ExpectedVersion = "",
    [string]$ExpectedPlatform = "win32",
    [string]$ExpectedArchitecture = "x64",
    [string]$PublicKey = $env:VIBECRAFTED_RUNTIME_PACK_PUBLIC_KEY
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Die {
    param([string]$Message)
    Write-Error "Runtime Pack install failed: $Message"
    exit 1
}

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-FileSha256Hex {
    param([string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            $bytes = $sha.ComputeHash($stream)
            return ([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
        }
        finally { $stream.Dispose() }
    }
    finally { $sha.Dispose() }
}

function Test-RuntimePackSignature {
    param(
        [string]$Archive,
        [string]$Signature,
        [string]$KeyPath
    )
    if (-not (Test-Path -LiteralPath $Signature)) {
        Die "Runtime Pack signature is missing: $Signature"
    }
    if (-not (Test-Path -LiteralPath $KeyPath)) {
        Die "trusted Runtime Pack public key is missing: $KeyPath"
    }
    $openssl = Get-Command openssl -ErrorAction SilentlyContinue
    if ($openssl) {
        & openssl dgst -sha256 -verify $KeyPath -signature $Signature $Archive 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Die "Runtime Pack signature verification failed"
    }
    try {
        $pem = Get-Content -LiteralPath $KeyPath -Raw
        $rsa = [System.Security.Cryptography.RSA]::Create()
        $rsa.ImportFromPem($pem)
        $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash(
            [System.IO.File]::ReadAllBytes($Archive)
        )
        $sig = [System.IO.File]::ReadAllBytes($Signature)
        $ok = $rsa.VerifyHash(
            $hash,
            $sig,
            [System.Security.Cryptography.HashAlgorithmName]::SHA256,
            [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
        )
        if (-not $ok) { Die "Runtime Pack signature verification failed" }
        return
    }
    catch {
        Die "cannot verify Runtime Pack signature (need openssl or PowerShell 7+ RSA PEM): $($_.Exception.Message)"
    }
}

function Test-ChecksumFile {
    param([string]$Archive, [string]$ChecksumPath)
    if (-not (Test-Path -LiteralPath $ChecksumPath)) {
        Die "Runtime Pack checksum is missing: $ChecksumPath"
    }
    $expected = ((Get-Content -LiteralPath $ChecksumPath -Raw) -split "\s+")[0].ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{64}$') {
        Die "Runtime Pack checksum file is invalid: $ChecksumPath"
    }
    $actual = Get-FileSha256Hex $Archive
    if ($actual -ne $expected) {
        Die "Runtime Pack checksum mismatch"
    }
}

function Get-WindowsTar {
    $systemTar = Join-Path $env:SystemRoot "System32\tar.exe"
    if (Test-Path -LiteralPath $systemTar) { return $systemTar }
    Die "Windows System32 tar.exe is required to extract the Runtime Pack (Git tar treats C: as a remote host)"
}

function Get-NativeArch {
    if ($env:PROCESSOR_ARCHITECTURE -match 'ARM64') { return "arm64" }
    return "x64"
}

if ($Uninstall -and $VerifyOnly) {
    Die "--VerifyOnly cannot be combined with --Uninstall"
}
if ($DryRun -and -not $Uninstall) {
    Die "--DryRun is only valid with --Uninstall"
}

$repoRoot = Get-RepoRoot
if (-not $ExpectedVersion) {
    $versionFile = Join-Path $repoRoot "VERSION"
    if (Test-Path -LiteralPath $versionFile) {
        $ExpectedVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
    }
}
if ($ExpectedArchitecture -eq "") {
    $ExpectedArchitecture = Get-NativeArch
}

if ($Uninstall -and -not $Pack) {
    $runtimeHome = $env:VIBECRAFTED_RUNTIME_HOME
    if (-not $runtimeHome) {
        $local = $env:LOCALAPPDATA
        if (-not $local) { $local = Join-Path $env:USERPROFILE "AppData\Local" }
        $runtimeHome = Join-Path $local "Vibecrafted"
    }
    $receipt = Join-Path $runtimeHome "install-receipt.json"
    if (-not (Test-Path -LiteralPath $receipt)) {
        Write-Output '{"schema":"vibecrafted.runtime-uninstall-result.v1","status":"absent"}'
        exit 0
    }
    $current = Join-Path $runtimeHome "tools\vibecrafted-current"
    if (Test-Path -LiteralPath $current) {
        $generation = (Resolve-Path $current).Path
        $packPython = Join-Path $generation "bin\python.exe"
        $packInstaller = Join-Path $generation "scripts\vetcoders_install.py"
        if (-not (Test-Path -LiteralPath $packPython)) { Die "installed Runtime Pack Python missing: $packPython" }
        if (-not (Test-Path -LiteralPath $packInstaller)) { Die "installed Runtime Pack installer missing: $packInstaller" }
        $arguments = @($packInstaller, "runtime-uninstall")
        if ($DryRun) { $arguments += "--dry-run" }
        & $packPython @arguments
        exit $LASTEXITCODE
    }
    Die "installed Runtime Pack projection is missing; pass -Pack to recover from the receipt"
}

if (-not $Pack) {
    $dist = Join-Path $repoRoot "dist"
    $candidates = @()
    if (Test-Path -LiteralPath $dist) {
        $candidates = @(Get-ChildItem -LiteralPath $dist -Filter "Vibecrafted_RuntimePack_*-$ExpectedPlatform-$ExpectedArchitecture.tar.gz" -File)
    }
    if ($candidates.Count -eq 1) {
        $Pack = $candidates[0].FullName
    }
    elseif ($candidates.Count -gt 1) {
        Die "multiple Runtime Packs in dist; set VIBECRAFTED_RUNTIME_PACK explicitly"
    }
    else {
        Die "no $ExpectedPlatform/$ExpectedArchitecture Runtime Pack found; set VIBECRAFTED_RUNTIME_PACK to the prebuilt release asset"
    }
}

if (-not (Test-Path -LiteralPath $Pack)) {
    Die "cannot resolve Runtime Pack path: $Pack"
}
$Pack = (Resolve-Path -LiteralPath $Pack).Path
if ($Pack -notlike "*.tar.gz") {
    Die "Runtime Pack must be the canonical .tar.gz carrier: $Pack"
}

$hostArch = Get-NativeArch
if ($ExpectedArchitecture -and $ExpectedArchitecture -ne $hostArch) {
    Die "Runtime Pack architecture $ExpectedArchitecture does not match host $hostArch"
}

$checksum = "$Pack.sha256"
$signature = "$Pack.sig"
if (-not $PublicKey) {
    $PublicKey = Join-Path $repoRoot "vibecrafted-core\vibecrafted_core\trust\vibecrafted-signing-v1.pub"
}

Test-ChecksumFile -Archive $Pack -ChecksumPath $checksum
Test-RuntimePackSignature -Archive $Pack -Signature $signature -KeyPath $PublicKey

$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("vibecrafted-runtime-pack-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $windowsTar = Get-WindowsTar
    $listing = & $windowsTar -tzf $Pack 2>&1
    if ($LASTEXITCODE -ne 0) { Die "Runtime Pack archive cannot be listed" }
    $archiveRoot = $null
    foreach ($member in $listing) {
        $name = [string]$member
        if ([string]::IsNullOrWhiteSpace($name)) { Die "Runtime Pack archive contains an empty member" }
        if ($name.StartsWith("/") -or $name.Contains("..")) {
            Die "unsafe Runtime Pack archive member: $name"
        }
        $memberRoot = ($name -split "/")[0]
        if (-not $archiveRoot) { $archiveRoot = $memberRoot }
        elseif ($memberRoot -ne $archiveRoot) {
            Die "Runtime Pack archive must contain one root directory"
        }
    }
    if (-not $archiveRoot) { Die "Runtime Pack archive is empty" }
    & $windowsTar -xzf $Pack -C $temporary
    if ($LASTEXITCODE -ne 0) { Die "Runtime Pack archive extraction failed" }
    $payloadRoot = Join-Path $temporary $archiveRoot
    if (-not (Test-Path -LiteralPath $payloadRoot)) {
        Die "runtime payload missing: $payloadRoot"
    }

    $packPython = Join-Path $payloadRoot "bin\python.exe"
    $packInstaller = Join-Path $payloadRoot "scripts\vetcoders_install.py"
    if (-not (Test-Path -LiteralPath $packPython)) { Die "Runtime Pack Python missing: $packPython" }
    if (-not (Test-Path -LiteralPath $packInstaller)) { Die "Runtime Pack installer missing: $packInstaller" }

    $env:PYTHONPATH = (Join-Path $payloadRoot "vibecrafted-core")
    $env:PYTHONNOUSERSITE = "1"
    $contract = @(
        "-m", "vibecrafted_core.runtime_pack_contract", "verify",
        "--root", $payloadRoot,
        "--carrier-basename", [IO.Path]::GetFileName($Pack),
        "--expected-version", $ExpectedVersion,
        "--expected-platform", $ExpectedPlatform,
        "--expected-architecture", $ExpectedArchitecture
    )
    if ($ExpectedSourceRevision) { $contract += @("--expected-source-revision", $ExpectedSourceRevision) }
    if ($ExpectedTerminalRevision) { $contract += @("--expected-terminal-revision", $ExpectedTerminalRevision) }
    if ($ExpectedFrameRevision) { $contract += @("--expected-frame-revision", $ExpectedFrameRevision) }
    $contractOutput = & $packPython @contract
    if ($LASTEXITCODE -ne 0) { Die "Runtime Pack internal provenance verification failed" }
    if ($VerifyOnly) {
        Write-Output $contractOutput
        exit 0
    }
    if ($Uninstall) {
        $arguments = @($packInstaller, "runtime-uninstall")
        if ($DryRun) { $arguments += "--dry-run" }
    }
    else {
        $arguments = @($packInstaller, "runtime-install", "--payload-root", $payloadRoot)
    }
    & $packPython @arguments
    exit $LASTEXITCODE
}
finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
    }
}
