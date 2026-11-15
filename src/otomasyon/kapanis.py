"""Safe shutdown (Windows): only when idle, no fullscreen app, before the cut-off time; 5-min cancellable warning."""
import ctypes
import time
from datetime import datetime

from .ortam import CONFIG, WINDOWS, calistir, log

C = CONFIG["gece"]
# SHQueryUserNotificationState: 2=busy (fullscreen app), 3=D3D fullscreen (game), 4=presentation mode
_MESGUL = {2: "tam ekran uygulama", 3: "tam ekran oyun", 4: "sunum modu"}


class _LII(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def bosta_dakika() -> float:
    lii = _LII(ctypes.sizeof(_LII), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 60000


def engel() -> str | None:
    """Reason not to shut down right now, or None."""
    durum = ctypes.c_int()
    ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(durum))
    if durum.value in _MESGUL:
        return _MESGUL[durum.value]
    if (b := bosta_dakika()) < C["bosta_dakika"]:
        return f"kullaniliyor (bosta {b:.0f} dk)"
    return None


def _son_dakika() -> bool:
    h, m = map(int, C["son_deneme"].split(":"))
    simdi = datetime.now()
    return simdi.hour < 12 and (simdi.hour, simdi.minute) >= (h, m)


def kapat(deneme: bool, bekleme_sn: int = 1800) -> dict:
    if not WINDOWS:
        return {"durum": "windows degil", "kapandi": False}
    while True:
        if _son_dakika():
            log("kapanis", f"{C['son_deneme']} gecti, kapanmiyor")
            return {"durum": f"vazgecildi ({C['son_deneme']} gecti)", "kapandi": False}
        neden = engel()
        if neden is None:
            if deneme:
                log("kapanis", "DENEME: kosullar uygun, kapanirdi")
                return {"durum": "deneme: kapanirdi", "kapandi": False}
            calistir(["shutdown", "/s", "/t", str(C["uyari_saniye"]), "/c",
                      "Gece islerini bitirdim, 5 dakika sonra kapaniyorum. Iptal: shutdown /a"])
            log("kapanis", "kapanis baslatildi (5 dk uyari)")
            return {"durum": "kapanis baslatildi", "kapandi": True}
        log("kapanis", f"ertelendi: {neden}")
        if deneme:
            return {"durum": f"deneme: ertelenirdi ({neden})", "kapandi": False}
        time.sleep(bekleme_sn)
