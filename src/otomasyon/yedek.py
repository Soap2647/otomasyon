"""Nightly Drive backup with rclone sync (+ Sunday second copy and check)."""
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

from .ortam import CONFIG, calistir, log

C = CONFIG["yedek"]
RCLONE = shutil.which("rclone") or "rclone"
_BOYUT = {"": 1, "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}


def _uzak(kok: str) -> bool:
    """'gdrive:a/b' is an rclone remote; 'G:\\a' is a local drive letter."""
    return re.match(r"^[\w-]{2,}:", kok) is not None


def _alt(kok: str, *parca: str) -> str:
    return ("/" if _uzak(kok) else "\\").join([kok.rstrip("/\\"), *parca])


def _yol(p: str) -> Path:
    return Path(p).expanduser()


def _ortak(deneme: bool) -> list[str]:
    # Drive desktop mount: preallocation makes it report wrong sizes, and it keeps mtimes only to the millisecond.
    # Parallel transfers race on mkdir ("already exists") and .partial renames fail there, so: 1 transfer, --inplace.
    a = ["--fast-list", "--transfers", "1", "--checkers", "16", "--inplace", "--retries", "5", "--low-level-retries", "20",
         "--local-no-preallocate", "--modify-window", "1s", "--log-level", "NOTICE" if deneme else "ERROR"]
    for h in C["haric"]:
        a += ["--exclude", h]
    return a + (["--dry-run"] if deneme else [])


def _ozet(cikti: str) -> tuple[int, int]:
    """Count files/bytes rclone would copy in a dry run."""
    n = b = 0
    for m in re.finditer(r"Skipped (?:copy|update modification time).*?\(size ([\d.]+)(\w*)\)", cikti):
        n += 1
        b += float(m.group(1)) * _BOYUT.get(m.group(2).rstrip("B"), 1)
    return n, int(b)


def yedekle(deneme: bool) -> dict:
    bugun = date.today().isoformat()
    if not _uzak(C["hedef"]) and not Path(C["hedef"]).parent.parent.exists():  # Drive app must be running/mounted
        log("yedek", f"hedef bulunamadi: {C['hedef']} (Drive uygulamasi kapali mi?)")
        return {"kaynaklar": [], "ok": False, "hata": "Drive klasoru bulunamadi"}
    sonuc = {"kaynaklar": [], "ok": True}
    for k in C["kaynak"]:
        yol = _yol(k["yol"])
        if not yol.exists():
            sonuc["kaynaklar"].append({"ad": k["ad"], "durum": "yok, atlandi"})
            continue
        cmd = [RCLONE, "sync", str(yol), _alt(C["hedef"], k["ad"]), "--backup-dir", _alt(C["eski"], bugun, k["ad"])] + _ortak(deneme)
        r = calistir(cmd)
        kayit = {"ad": k["ad"], "rc": r.returncode}
        if deneme:
            kayit["kopyalanacak_dosya"], kayit["kopyalanacak_bayt"] = _ozet(r.stderr)
        if r.returncode != 0:
            sonuc["ok"] = False
            kayit["hata"] = r.stderr.strip().splitlines()[-1:] if r.stderr else []
        log("yedek", f"{k['ad']}: rc={r.returncode} {kayit.get('kopyalanacak_dosya', '')}")
        sonuc["kaynaklar"].append(kayit)
    dosyalar = [str(_yol(d)) for d in C["dosya"] if _yol(d).exists()]
    for d in dosyalar:
        r = calistir([RCLONE, "copyto", d, _alt(C["hedef"], "dosyalar", Path(d).name), "--local-no-preallocate"]
                     + (["--dry-run"] if deneme else []))
        sonuc["ok"] &= r.returncode == 0
    if not deneme:
        sinir = (date.today() - timedelta(days=C["eski_gun"])).isoformat()
        r = calistir([RCLONE, "lsf", C["eski"], "--dirs-only"])
        for klasor in r.stdout.split():
            if klasor.rstrip("/") < sinir:
                calistir([RCLONE, "purge", _alt(C["eski"], klasor.rstrip("/"))])
                log("yedek", f"90 gunden eski silindi: {klasor}")
    return sonuc


def ikinci_kopya(deneme: bool) -> dict:
    """Sunday: mirror to second account and verify. Skipped if gdrive2 remote is not configured."""
    remote = C["ikinci_kopya"].split(":")[0] + ":"
    if remote not in calistir([RCLONE, "listremotes"]).stdout.split():
        return {"durum": f"{remote} tanimli degil, atlandi", "ok": None}
    r = calistir([RCLONE, "sync", C["hedef"], C["ikinci_kopya"], "--fast-list", "--drive-server-side-across-configs"]
                 + (["--dry-run"] if deneme else []))
    c = calistir([RCLONE, "check", C["hedef"], C["ikinci_kopya"], "--one-way", "--fast-list"])
    return {"sync_rc": r.returncode, "check_rc": c.returncode, "ok": r.returncode == 0 and c.returncode == 0}
