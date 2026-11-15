"""Bot state in one JSON file: per-day counters/message ids and one list of items ("isler").

Item: {id, tur: etkinlik|son|yapilacak, metin, gun: "YYYY-MM-DD"|None, saat: "HH:MM"|None, bitti, iptal}
  etkinlik  -> has gun+saat; reminded before, shown in that day's plan
  son       -> deadline (gun); countdown in morning/evening messages
  yapilacak -> plain task; optional gun = "not before this day"
"""
import json
import threading
from datetime import date

from .ortam import STATE

_DOSYA = STATE / "bot.json"
_KILIT = threading.Lock()


def oku() -> dict:
    try:
        d = json.loads(_DOSYA.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        d = {"gun": {}}
    d.setdefault("isler", [])
    _gocet(d)
    return d


def _gocet(d: dict) -> None:
    """One-time migration from the old todo/notlar lists."""
    for t in d.pop("todo", []):
        ekle(d, "yapilacak", t["metin"], t.get("tarih"), None, bitti=t.get("bitti", False))
    for n in d.pop("notlar", []):
        gun, saat = n["zaman"][:10], n["zaman"][11:16]
        ekle(d, "etkinlik", n["metin"], gun, saat, iptal=n.get("iptal", False))


def yaz(d: dict) -> None:
    with _KILIT:
        tmp = _DOSYA.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        tmp.replace(_DOSYA)


def gun(d: dict, g: date | None = None) -> dict:
    """Today's record (created on demand): sesli, sabah_id, yarin_id, vitamin, durtuldu, hatirlatilan."""
    k = (g or date.today()).isoformat()
    return d["gun"].setdefault(k, {"sesli": 0, "vitamin": False, "durtuldu": False, "hatirlatilan": []})


def ekle(d: dict, tur: str, metin: str, gun: str | None, saat: str | None, **ek) -> dict:
    yeni = {"id": max((x["id"] for x in d["isler"]), default=0) + 1, "tur": tur, "metin": metin,
            "gun": gun or None, "saat": saat or None, "bitti": False, "iptal": False, **ek}
    d["isler"].append(yeni)
    return yeni


def bul(d: dict, id_: int) -> dict | None:
    return next((x for x in d["isler"] if x["id"] == id_), None)


def acik(d: dict) -> list[dict]:
    return [x for x in d["isler"] if not x["bitti"] and not x["iptal"]]
