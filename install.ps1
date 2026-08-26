#Requires -Version 5.1
<#
.SYNOPSIS
    Native Windows entry point for the Vibecrafted Runtime Pack.

.DESCRIPTION
    Installs the prebuilt Runtime Pack for this host. Does not require WSL,
    Homebrew, an app bundle, or a developer toolchain. GUI/App is optional;
    the runtime is the product.

.EXAMPLE
    PS> .\install.ps1
    PS> $env:VIBECRAFTED_RUNTIME_PACK = 'C:\path\Vibecrafted_RuntimePack_4.3.0-win32-x64.tar.gz'; .\install.ps1
#>

[CmdletBinding()]
param(
    [string]$Pack = $env:VIBECRAFTED_RUNTIME_PACK,
    [switch]$Uninstall,
    [switch]$VerifyOnly,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Write-Banner {
    param([string]$Message)
    Write-Host ""
    Write-Host "  Vibecrafted (Windows Runtime Pack)" -ForegroundColor Cyan
    Write-Host "  ---------------------------------"
    Write-Host "  $Message"
    Write-Host ""
}

$psVersion = $PSVersionTable.PSVersion
if ($psVersion.Major -lt 5 -or ($psVersion.Major -eq 5 -and $psVersion.Minor -lt 1)) {
    Write-Host "  ERROR: PowerShell 5.1 or newer is required." -ForegroundColor Red
    exit 2
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $repoRoot "scripts\install-runtime-pack.ps1"
if (-not (Test-Path -LiteralPath $installer)) {
    Write-Banner "Runtime Pack installer is missing: $installer"
    exit 1
}

Write-Banner "Installing the native Windows Runtime Pack. WSL is not required."
$forward = @{
    ExpectedPlatform = "win32"
}
if ($Pack) { $forward["Pack"] = $Pack }
if ($Uninstall) { $forward["Uninstall"] = $true }
if ($VerifyOnly) { $forward["VerifyOnly"] = $true }
if ($DryRun) { $forward["DryRun"] = $true }
& $installer @forward
exit $LASTEXITCODE
