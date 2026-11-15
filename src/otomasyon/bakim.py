"""winget upgrades (pinned packages excluded) and disk health. Windows-only parts are guarded."""
import shutil

from .ortam import CONFIG, WINDOWS, calistir, log

WG = ["--accept-source-agreements", "--disable-interactivity"]


def guncelle(deneme: bool) -> dict:
    if not WINDOWS:
        return {"durum": "windows degil, atlandi", "ok": None}
    pinli = calistir(["winget", "pin", "list", *WG]).stdout
    eksik_pin = [p for p in CONFIG["guncelle"]["pin"] if p not in pinli]
    liste = calistir(["winget", "upgrade", *WG]).stdout
    adaylar = [l.split()[-4] for l in liste.splitlines() if l.count(".") >= 2 and len(l.split()) >= 4 and "winget" in l]
    if deneme:
        return {"durum": "deneme", "guncellenecek": adaylar, "eksik_pin": eksik_pin, "ok": True}
    if eksik_pin:
        # pins are created once during setup (needs approval); never update unpinned critical tools
        return {"durum": "pinler eksik, guncelleme atlandi", "eksik_pin": eksik_pin, "ok": False}
    r = calistir(["winget", "upgrade", "--all", "--silent", "--accept-package-agreements", *WG])
    log("guncelle", f"rc={r.returncode}")
    return {"durum": "tamam" if r.returncode == 0 else "hata", "rc": r.returncode, "adaylar": adaylar, "ok": r.returncode == 0}


def saglik() -> dict:
    uyarilar = []
    esik = CONFIG["saglik"]["disk_esik"]
    for kok in (["C:\\", "D:\\"] if WINDOWS else ["/"]):
        try:
            u = shutil.disk_usage(kok)
        except OSError:
            continue
        oran = round(u.used / u.total * 100)
        if oran >= esik:
            uyarilar.append(f"{kok} %{oran} dolu")
    if WINDOWS:
        ps = ("Get-PhysicalDisk | ForEach-Object { $r = $_ | Get-StorageReliabilityCounter -EA SilentlyContinue; "
              "'{0}|{1}|{2}|{3}' -f $_.FriendlyName, $_.HealthStatus, $r.Wear, $r.Temperature }")
        for satir in calistir(["powershell", "-NoProfile", "-Command", ps]).stdout.splitlines():
            ad, saglik_, asinma, _isi = (satir.split("|") + ["", "", ""])[:4]
            if saglik_ and saglik_ != "Healthy":
                uyarilar.append(f"{ad}: SMART {saglik_}")
            if asinma.isdigit() and int(asinma) >= 80:
                uyarilar.append(f"{ad}: asinma %{asinma}")
    log("saglik", "; ".join(uyarilar) or "sorun yok")
    return {"uyarilar": uyarilar, "ok": not uyarilar}
