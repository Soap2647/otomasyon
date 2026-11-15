# Points rclone's gdrive remote at our own Google OAuth client (from .env) and re-authorizes in the browser.
#   powershell -ExecutionPolicy Bypass -File "D:\Mevcut Projeler\otomasyon\kurulum\rclone-baglan.ps1" [-Remote gdrive]
param([string]$Remote = 'gdrive')
$env_ = @{}
Get-Content (Join-Path $PSScriptRoot '..\.env') | Where-Object { $_ -match '^\s*([A-Z_0-9]+)\s*=\s*(.*)$' } |
  ForEach-Object { $env_[$Matches[1]] = $Matches[2].Trim('"', "'", ' ') }
if (-not $env_['GOOGLE_CLIENT_ID'] -or -not $env_['GOOGLE_CLIENT_SECRET']) { throw '.env icinde GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET yok' }

if ((rclone listremotes) -notcontains "${Remote}:") {
  rclone config create $Remote drive scope=drive client_id=$($env_['GOOGLE_CLIENT_ID']) client_secret=$($env_['GOOGLE_CLIENT_SECRET'])
} else {
  rclone config update $Remote client_id=$($env_['GOOGLE_CLIENT_ID']) client_secret=$($env_['GOOGLE_CLIENT_SECRET']) --non-interactive | Out-Null
  rclone config reconnect "${Remote}:"   # opens the browser for sign-in
}
rclone about "${Remote}:"
