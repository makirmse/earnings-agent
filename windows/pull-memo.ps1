# pull-memo.ps1 -- pull an institutional memo from the Mac Mini over Tailscale.
#
# Usage from any Windows terminal (cmd or PowerShell), after one-time setup:
#
#   memo AAPL          # find the newest memo with AAPL in the filename, pull
#                      # it to Documents\Memos\, and open it.
#   memo               # show a numbered list of all memos and let you pick.
#   memo aapl 2025     # match files containing both substrings (any order).
#
# One-time setup (do this once on your Windows machine):
#
#   1. Clone or download this repo to anywhere on disk, e.g. C:\tools\earnings-agent.
#   2. Add the windows\ folder to your user PATH:
#        - Start menu -> "Edit environment variables for your account"
#        - Path -> New -> C:\tools\earnings-agent\windows
#        - OK, then open a fresh terminal.
#   3. Make sure you can already run `ssh projectx@100.99.13.95` from this
#      machine without typing a password (Tailscale + an SSH key in
#      %USERPROFILE%\.ssh\ ). If `ssh` itself prompts for a password every
#      time, this script will too.
#
# All defaults below can be overridden with environment variables, no edits
# to this file needed:
#
#   MEMO_SSH_HOST       e.g. projectx@100.99.13.95
#   MEMO_REMOTE_PATH    e.g. ~/ProjectX/research engine/institutional memo's
#   MEMO_LOCAL_CACHE    e.g. C:\Users\you\Documents\Memos

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Query
)

$ErrorActionPreference = 'Stop'

$SshHost     = if ($env:MEMO_SSH_HOST)    { $env:MEMO_SSH_HOST }    else { 'projectx@100.99.13.95' }
$RemotePath  = if ($env:MEMO_REMOTE_PATH) { $env:MEMO_REMOTE_PATH } else { "~/ProjectX/research engine/institutional memo's" }
$LocalCache  = if ($env:MEMO_LOCAL_CACHE) { $env:MEMO_LOCAL_CACHE } else { Join-Path $env:USERPROFILE 'Documents\Memos' }

New-Item -ItemType Directory -Path $LocalCache -Force | Out-Null

function ConvertTo-ShellPath {
    # Bash-quote a remote path. Leaves a leading ~/ unquoted so tilde expands.
    param([string]$Path)
    if ($Path.StartsWith('~/')) {
        return '~/' + "'" + ($Path.Substring(2) -replace "'", "'\''") + "'"
    }
    if ($Path -eq '~') { return '~' }
    return "'" + ($Path -replace "'", "'\''") + "'"
}

$remoteQ = ConvertTo-ShellPath $RemotePath

Write-Host "Listing memos on $SshHost ..." -ForegroundColor DarkGray
$listing = & ssh -o BatchMode=yes -o ConnectTimeout=10 $SshHost "ls -1t -- $remoteQ" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $listing -ForegroundColor Red
    throw "Could not list memos. Check that 'ssh $SshHost' works and that the path exists: $RemotePath"
}

$allFiles = @($listing -split "`r?`n" | Where-Object { $_.Trim() -ne '' })
if ($allFiles.Count -eq 0) {
    Write-Host "No files found in $RemotePath" -ForegroundColor Yellow
    exit 0
}

if ($Query -and $Query.Count -gt 0) {
    $needles = $Query | ForEach-Object { $_.ToLower() }
    $candidates = @($allFiles | Where-Object {
        $name = $_.ToLower()
        $matchAll = $true
        foreach ($n in $needles) { if (-not $name.Contains($n)) { $matchAll = $false; break } }
        $matchAll
    })
    if ($candidates.Count -eq 0) {
        Write-Host ("No memo matches '{0}'. Available memos:" -f ($Query -join ' ')) -ForegroundColor Yellow
        $allFiles | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
    $picked = $candidates[0]
    if ($candidates.Count -gt 1) {
        Write-Host ("Multiple matches for '{0}':" -f ($Query -join ' ')) -ForegroundColor Cyan
        for ($i = 0; $i -lt $candidates.Count; $i++) {
            Write-Host ("  [{0}] {1}" -f ($i + 1), $candidates[$i])
        }
        $sel = Read-Host "Pick (1-$($candidates.Count), Enter = newest)"
        if ($sel -match '^\d+$') {
            $idx = [int]$sel - 1
            if ($idx -ge 0 -and $idx -lt $candidates.Count) { $picked = $candidates[$idx] }
        }
    }
} else {
    Write-Host "Available memos in $RemotePath (newest first):" -ForegroundColor Cyan
    for ($i = 0; $i -lt $allFiles.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $allFiles[$i])
    }
    $sel = Read-Host "Pick a number (Enter to cancel)"
    if (-not ($sel -match '^\d+$')) { exit 0 }
    $idx = [int]$sel - 1
    if ($idx -lt 0 -or $idx -ge $allFiles.Count) { throw "Out of range." }
    $picked = $allFiles[$idx]
}

$remoteFile  = "$RemotePath/$picked"
$localFile   = Join-Path $LocalCache $picked

Write-Host "Pulling: $picked" -ForegroundColor Green

# Use sftp with a batch script. sftp sends the path literally via the SFTP
# protocol, so we don't need any shell quoting on the remote side. sftp
# accepts forward slashes for the local path on Windows.
$localForSftp = $localFile -replace '\\','/'
$batch = New-TemporaryFile
try {
    Set-Content -LiteralPath $batch -Encoding ASCII -Value @(
        "get `"$remoteFile`" `"$localForSftp`""
    )
    & sftp -q -b $batch $SshHost
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $localFile)) {
        throw "sftp failed for: $remoteFile"
    }
} finally {
    Remove-Item -LiteralPath $batch -ErrorAction SilentlyContinue
}

Write-Host "Saved: $localFile" -ForegroundColor Green
Start-Process -FilePath $localFile
