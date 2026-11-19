# Starts Syncthing at every logon of this user, hidden, restarts on failure. No admin needed.
# Syncs state\ortak (gece-son.json) and the Obsidian vault with the UNO Q (kahya).
#   powershell -ExecutionPolicy Bypass -File "D:\Mevcut Projeler\otomasyon\kurulum\syncthing-gorev.ps1"
# Remove: Unregister-ScheduledTask -TaskName "Otomasyon - Syncthing" -Confirm:$false
# winget puts it under a versioned folder that changes on the nightly upgrade, so the newest exe is looked up at each start
$bul = "`$e = Get-ChildItem `"`$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Syncthing.Syncthing_*\*\syncthing.exe`" | Sort-Object LastWriteTime | Select-Object -Last 1; & `$e.FullName serve --no-browser --no-console; exit `$LASTEXITCODE"
$eylem = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -Command `"$bul`""
$tetik = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$kim = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Otomasyon - Syncthing' -Action $eylem -Trigger $tetik -Settings $ayar -Principal $kim `
  -Description 'Syncthing: kasa + state/ortak <-> kahya (otomasyon projesi)' -Force | Out-Null
Start-ScheduledTask -TaskName 'Otomasyon - Syncthing'
Get-ScheduledTask -TaskName 'Otomasyon - Syncthing' | Select-Object TaskName, State
