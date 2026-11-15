# Registers the nightly task. Run ONCE as Administrator, after approval:
#   powershell -ExecutionPolicy Bypass -File "D:\Mevcut Projeler\otomasyon\kurulum\gorev-kaydet.ps1"
# Remove later with:  Unregister-ScheduledTask -TaskName "Otomasyon - Gece" -Confirm:$false
$proje = 'D:\Mevcut Projeler\otomasyon'
$uv = (Get-Command uv).Source
$eylem = New-ScheduledTaskAction -Execute $uv -Argument 'run --project . python -m otomasyon.gece --uygula' -WorkingDirectory $proje

# Sun-Thu nights -> 00:30 on Mon-Fri; Fri/Sat nights -> 01:00 on Sat/Sun
$haftaici = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At '00:30'
$haftasonu = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday, Sunday -At '01:00'

# Missed runs are NOT caught up (otherwise booting in the morning would back up and shut down).
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 5) -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$ayar.StartWhenAvailable = $false

# Interactive user session (idle/fullscreen detection), highest privileges (winget, SMART counters).
$kim = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName 'Otomasyon - Gece' -Action $eylem -Trigger $haftaici, $haftasonu -Settings $ayar `
  -Principal $kim -Description 'Drive yedegi, git wip, winget, saglik, guvenli kapanis (otomasyon projesi)' -Force
