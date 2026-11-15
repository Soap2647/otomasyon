"""Shared plumbing: config.toml, .env secrets, state/log files. Portable (Windows + Debian)."""
import json
import os
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
CONFIG = tomllib.loads((KOK / "config.toml").read_text(encoding="utf-8"))
WINDOWS = sys.platform == "win32"
STATE = Path(os.environ.get("OTOMASYON_STATE") or (r"D:\Dev\otomasyon\state" if WINDOWS else "~/.local/state/otomasyon")).expanduser()
STATE.mkdir(parents=True, exist_ok=True)


def _env() -> dict[str, str]:
    f = KOK / ".env"
    if not f.exists():
        return {}
    out = {}
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sir(ad: str) -> str | None:
    return os.environ.get(ad) or _env().get(ad)


def log(adim: str, mesaj: str) -> None:
    satir = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{adim}] {mesaj}"
    print(satir, flush=True)
    with open(STATE / "gece.log", "a", encoding="utf-8") as f:
        f.write(satir + "\n")


def kaydet(ad: str, veri: dict) -> None:
    veri = {"zaman": datetime.now().isoformat(timespec="seconds"), **veri}
    (STATE / f"{ad}.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def calistir(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
