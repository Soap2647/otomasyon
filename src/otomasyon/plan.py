"""A day's plan from all sources: courses + Google Calendar + bot items. Used by messages and the assistant context."""
from datetime import date, timedelta
from html import escape as e

from . import ders, durum, takvim
from .ortam import log

KALAN_GUN = 14


def zaman_cizelgesi(g: date, d: dict) -> list[tuple[str, str]]:
    """[(HH:MM or 'Tüm gün', text)] sorted; courses, calendar events and timed bot items together."""
    out = [(x["baslangic"], f"{x['ad']} · {x['yer']}") for x in ders.gunun_dersleri(g)]
    try:
        tatil, etkinlikler = takvim.tatil(g), takvim.etkinlikler(g, g)
        if tatil:
            out.append(("Tüm gün", f"🎉 {tatil}"))
        out += [("Tüm gün" if ev["tum_gun"] else ev["bas"].strftime("%H:%M"), ev["ad"]) for ev in etkinlikler]
    except Exception as ex:
        log("plan", f"takvim: {ex}")
    out += [(x["saat"], f"📌 {x['metin']}") for x in durum.acik(d) if x["tur"] == "etkinlik" and x["gun"] == g.isoformat()]
    return sorted(out, key=lambda x: ("0" if x[0] == "Tüm gün" else x[0]))


def son_tarihler(g: date, d: dict) -> list[tuple[int, str]]:
    """[(days left, text)] for bot deadlines and ders.toml exams/assignments within KALAN_GUN days."""
    out = [(x["kalan"], x["ad"]) for x in ders.yaklasanlar(g, KALAN_GUN)]
    for x in durum.acik(d):
        if x["tur"] == "son" and x["gun"] and 0 <= (k := (date.fromisoformat(x["gun"]) - g).days) <= KALAN_GUN:
            out.append((k, x["metin"]))
    return sorted(out)


def yapilacaklar(g: date, d: dict) -> list[dict]:
    return [x for x in durum.acik(d) if x["tur"] == "yapilacak" and (not x["gun"] or x["gun"] <= g.isoformat())]


def kalan_yazi(k: int) -> str:
    return "bugün son gün" if k == 0 else "yarın son gün" if k == 1 else f"{k} gün kaldı"


def kart(x: dict, bugun: date | None = None) -> str:
    """One-line HTML card for a bot item."""
    from .mesaj import tarih_yazi
    bugun = bugun or date.today()
    g = date.fromisoformat(x["gun"]) if x["gun"] else None
    if x["tur"] == "etkinlik":
        return f"📌 <b>{tarih_yazi(g)} {x['saat']}</b> · {e(x['metin'])}"
    if x["tur"] == "son" and g:
        return f"⏳ {e(x['metin'])} · <b>{tarih_yazi(g)}</b> ({kalan_yazi((g - bugun).days)})"
    return f"📝 {e(x['metin'])}" + (f" · {tarih_yazi(g)}" if g else "")


def html_bolum(g: date, d: dict) -> list[str]:
    s = []
    if cizelge := zaman_cizelgesi(g, d):
        s += [f"<code>{z:>5}</code> {e(t)}" if z != "Tüm gün" else f"<code>  ●  </code> {e(t)}" for z, t in cizelge]
    else:
        s.append("Ders ya da etkinlik yok 🎈")
    if sonlar := son_tarihler(g, d):
        s.append("")
        s += [f"⏳ {e(t)} · <b>{kalan_yazi(k)}</b>" for k, t in sonlar]
    return s


def metin_ozet(bas: date, gun_sayisi: int, d: dict) -> str:
    """Plain-text context for the model: the next days' plan, deadlines and open tasks with ids."""
    from .mesaj import tarih_yazi
    s = []
    for i in range(gun_sayisi):
        g = bas + timedelta(days=i)
        satirlar = "; ".join(f"{z} {t}" for z, t in zaman_cizelgesi(g, d)) or "boş"
        s.append(f"{tarih_yazi(g)} ({g.isoformat()}): {satirlar}")
    s.append("Açık işler (id | tür | gün | saat | metin):")
    s += [f"{x['id']} | {x['tur']} | {x['gun'] or '-'} | {x['saat'] or '-'} | {x['metin']}" for x in durum.acik(d)] or ["(yok)"]
    return "\n".join(s)
