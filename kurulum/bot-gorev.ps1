# Starts the Telegram bot at every logon of this user, hidden (pythonw), restarts on failure. No admin needed.
#   powershell -ExecutionPolicy Bypass -File "D:\Mevcut Projeler\otomasyon\kurulum\bot-gorev.ps1"
# Remove: Unregister-ScheduledTask -TaskName "Otomasyon - Bot" -Confirm:$false
$proje = 'D:\Mevcut Projeler\otomasyon'
$eylem = New-ScheduledTaskAction -Execute "$proje\.venv\Scripts\pythonw.exe" -Argument '-m otomasyon.bot' -WorkingDirectory $proje
$tetik = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$tetik.Delay = 'PT30S'   # let Wi-Fi come up
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$kim = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Otomasyon - Bot' -Action $eylem -Trigger $tetik -Settings $ayar -Principal $kim `
  -Description 'Jarvis Telegram botu (otomasyon projesi)' -Force | Out-Null
Start-ScheduledTask -TaskName 'Otomasyon - Bot'
Get-ScheduledTask -TaskName 'Otomasyon - Bot' | Select-Object TaskName, State
