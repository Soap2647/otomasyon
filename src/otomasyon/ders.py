"""Timetable, exams and assignments from ders.toml (no model)."""
import tomllib
from datetime import date, datetime

from .ortam import KOK

GUNLER = ["pzt", "sal", "car", "per", "cum", "cmt", "paz"]


def _veri() -> dict:
    return tomllib.loads((KOK / "ders.toml").read_text(encoding="utf-8"))


def gunun_dersleri(gun: date) -> list[dict]:
    v = _veri()
    d = v["donem"]
    if not (d["baslangic"] <= gun <= d["bitis"]) or gun in d.get("tatil", []):
        return []
    kod = GUNLER[gun.weekday()]
    return sorted((x for x in v.get("ders", []) if x["gun"] == kod), key=lambda x: x["baslangic"])


def yaklasanlar(gun: date, ileri_gun: int = 14) -> list[dict]:
    """Exams and assignments due within the window: {ad, tarih, kalan, tur}."""
    v, out = _veri(), []
    for tur, alan in (("sinav", "tarih"), ("odev", "son")):
        for x in v.get(tur, []):
            t = x[alan].date() if isinstance(x[alan], datetime) else x[alan]
            kalan = (t - gun).days
            if 0 <= kalan <= ileri_gun:
                out.append({"ad": x["ad"], "tarih": x[alan], "kalan": kalan, "tur": tur})
    return sorted(out, key=lambda x: x["kalan"])


def satir(gun: date) -> str:
    dersler = gunun_dersleri(gun)
    return " · ".join(f"{x['baslangic']} {x['ad']} ({x['yer']})" for x in dersler) if dersler else "ders yok"
