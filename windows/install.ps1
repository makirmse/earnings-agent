# install.ps1 -- one-shot installer for the `memo` command on Windows.
#
# Run from a normal (non-admin) PowerShell prompt:
#
#   irm https://raw.githubusercontent.com/makirmse/earnings-agent/claude/mac-mini-memo-access-wfymit/windows/install.ps1 | iex
#
# Or, if you've already cloned the repo, just:  .\install.ps1
#
# What it does:
#   1. Copies pull-memo.ps1 + memo.cmd to %LOCALAPPDATA%\Memo\
#   2. Adds that folder to your user PATH (no admin needed)
#   3. Creates %USERPROFILE%\Documents\Memos\ for downloaded memos
#   4. Tests the SSH connection to the Mac Mini and reports back

[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Memo'),
    [string]$SshHost    = 'projectx@100.99.13.95',
    [string]$RemotePath = '/Users/projectx/research-engine/institutional_memos'
)

$ErrorActionPreference = 'Stop'

Write-Host "Installing memo command to: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$here = if ($PSScriptRoot) { $PSScriptRoot } else { $null }
$ps1Src = if ($here) { Join-Path $here 'pull-memo.ps1' } else { $null }
$cmdSrc = if ($here) { Join-Path $here 'memo.cmd' }     else { $null }

if ($ps1Src -and (Test-Path -LiteralPath $ps1Src)) {
    Copy-Item -LiteralPath $ps1Src -Destination (Join-Path $InstallDir 'pull-memo.ps1') -Force
    Copy-Item -LiteralPath $cmdSrc -Destination (Join-Path $InstallDir 'memo.cmd') -Force
    Write-Host "  Copied scripts from $here" -ForegroundColor DarkGray
} else {
    $base = 'https://raw.githubusercontent.com/makirmse/earnings-agent/claude/mac-mini-memo-access-wfymit/windows'
    Write-Host "  Downloading scripts from GitHub..." -ForegroundColor DarkGray
    Invoke-WebRequest -Uri "$base/pull-memo.ps1" -OutFile (Join-Path $InstallDir 'pull-memo.ps1') -UseBasicParsing
    Invoke-WebRequest -Uri "$base/memo.cmd"     -OutFile (Join-Path $InstallDir 'memo.cmd')     -UseBasicParsing
}

# Add InstallDir to the user PATH if it isn't already.
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $userPath) { $userPath = '' }
$onPath = ($userPath -split ';' | Where-Object { $_.TrimEnd('\') -ieq $InstallDir.TrimEnd('\') }).Count -gt 0
if (-not $onPath) {
    $newPath = if ($userPath) { "$userPath;$InstallDir" } else { $InstallDir }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    $env:Path = "$env:Path;$InstallDir"
    Write-Host "  Added $InstallDir to your user PATH" -ForegroundColor Green
} else {
    Write-Host "  Already on your user PATH" -ForegroundColor DarkGray
}

# Memo download folder.
$cache = Join-Path $env:USERPROFILE 'Documents\Memos'
New-Item -ItemType Directory -Path $cache -Force | Out-Null
Write-Host "  Memos will land in: $cache" -ForegroundColor DarkGray

# Quick connection test (non-fatal).
Write-Host ""
Write-Host "Testing SSH connection to $SshHost ..." -ForegroundColor Cyan
$probe = & ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new $SshHost "echo ok && ls -1 -- '$($RemotePath -replace "'","'\''")' 2>&1 | head -5" 2>&1
if ($LASTEXITCODE -eq 0 -and $probe -match 'ok') {
    Write-Host "Connection OK. Sample of memo folder:" -ForegroundColor Green
    ($probe -split "`r?`n" | Where-Object { $_ -and $_ -ne 'ok' }) | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "Couldn't reach the Mac Mini yet. Output:" -ForegroundColor Yellow
    $probe | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    Write-Host "Fix likely needed:" -ForegroundColor Yellow
    Write-Host "  - Make sure Tailscale is running on this machine and the Mac Mini." -ForegroundColor Yellow
    Write-Host "  - Confirm `ssh $SshHost` works manually (you may need to copy your" -ForegroundColor Yellow
    Write-Host "    Windows public key from %USERPROFILE%\.ssh\id_*.pub onto the Mac Mini's" -ForegroundColor Yellow
    Write-Host "    ~/.ssh/authorized_keys so it doesn't prompt for a password)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Open a NEW terminal, then try:" -ForegroundColor Cyan
Write-Host "  memo            # list all memos" -ForegroundColor White
Write-Host "  memo AAPL       # pull and open the newest AAPL memo" -ForegroundColor White
