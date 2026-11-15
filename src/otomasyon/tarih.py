"""Rule-based Turkish date/time parsing for quick notes (no model).

ayristir("cuma 14:00 diş randevusu") -> (datetime(..14:00), True, "diş randevusu")
ayristir("yarın annemi ara")          -> (datetime(yarın 00:00), False, "annemi ara")
ayristir("süt al")                     -> (None, False, "süt al")
"""
import re
from datetime import date, datetime, time, timedelta

AYLAR = {"ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
         "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12}
# longest first so "cumartesi" wins over "cuma", "pazartesi" over "pazar"
GUNLER = [("cumartesi", 5), ("pazartesi", 0), ("çarşamba", 2), ("carsamba", 2), ("perşembe", 3), ("persembe", 3),
          ("salı", 1), ("sali", 1), ("cuma", 4), ("pazar", 6)]
EK = r"(?:'?(?:y?[ae]|d[ae]|t[ae]|n[ae]|ü|u|ı|i|günü|gunu))?"   # 'ya, 'de, 'te, günü ...
DOLGU = re.compile(r"(?i)\b(saat|günü|gunu|da|de|te|ta|kadar|son gün|son gun)\b")
SON_TARIH = re.compile(r"(?i)\b(kadar|son gün|son gun|teslim|deadline)\b")


def _kes(metin: str, m: re.Match) -> str:
    return (metin[: m.start()] + " " + metin[m.end():]).strip()


def ayristir(metin: str, simdi: datetime | None = None) -> tuple[datetime | None, bool, str]:
    simdi = simdi or datetime.now()
    s = " " + metin.strip() + " "
    gun: date | None = None
    saat: time | None = None

    if m := re.search(r"(?i)\b(\d+|yarım|yarim)\s*(saat|dk|dakika)\s+sonra\b", s):
        n = 0.5 if m.group(1).lower() in ("yarım", "yarim") else int(m.group(1))
        dt = simdi + (timedelta(hours=n) if m.group(2).lower() == "saat" else timedelta(minutes=n))
        return dt.replace(second=0, microsecond=0), True, _temiz(_kes(s, m))

    # time: 14:00 / 14.30 / saat 9 / 14'te / akşam 7 / sabah 9 / öğlen
    if m := re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b(?!\.\d)", s):
        # "12.11" alone is a date; "14.00", "saat 9.30" or "6 kasım 14.10" are times
        tarih_gibi = m.group(0).count(".") and 1 <= int(m.group(2)) <= 12 and int(m.group(1)) >= 1
        baska_tarih = re.search(r"(?i)" + "|".join(list(AYLAR) + [a for a, _ in GUNLER] + ["bugün", "bugun", "yarın", "yarin"]), s)
        if not (tarih_gibi and not baska_tarih and not re.search(r"(?i)saat\s*$", s[: m.start()])):
            saat, s = time(int(m.group(1)), int(m.group(2))), _kes(s, m)
    if saat is None and (m := re.search(r"(?i)\b(sabah|öğlen|oglen|öğleden sonra|akşam|aksam|gece)?\s*(?:saat\s*)?([01]?\d|2[0-3])\s*'?(?:te|ta|de|da|’te|’de)\b", s)) \
            or saat is None and (m := re.search(r"(?i)\b(sabah|öğlen|oglen|öğleden sonra|akşam|aksam|gece)?\s*saat\s*([01]?\d|2[0-3])\b", s)) \
            or saat is None and (m := re.search(r"(?i)\b(sabah|öğleden sonra|akşam|aksam|gece)\s+([01]?\d)\b", s)):
        h, dilim = int(m.group(2)), (m.group(1) or "").lower()
        if dilim in ("akşam", "aksam", "öğleden sonra", "gece") and h < 12 or not dilim and 1 <= h <= 6:
            h += 12
        saat, s = time(h % 24, 0), _kes(s, m)
    if saat is None and (m := re.search(r"(?i)\b(öğlen|oglen)\b", s)):
        saat, s = time(12, 0), _kes(s, m)

    # day
    if m := re.search(r"(?i)\b(bugün|bugun|yarın|yarin|öbür ?gün|obur ?gun|ertesi gün)" + EK + r"\b", s):
        k = m.group(1).lower()
        gun = simdi.date() + timedelta(days=0 if k.startswith("bug") else 1 if k.startswith("yar") else 2)
        s = _kes(s, m)
    elif m := re.search(r"(?i)\b(\d{1,2})\s+(" + "|".join(AYLAR) + r")" + EK + r"(?:\s+(\d{4}))?\b", s):
        gun = _yil_ayarla(int(m.group(1)), AYLAR[m.group(2).lower()], m.group(3), simdi)
        s = _kes(s, m)
    elif m := re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?\b", s):
        gun = _yil_ayarla(int(m.group(1)), int(m.group(2)), m.group(3), simdi)
        s = _kes(s, m)
    else:
        for ad, wd in GUNLER:
            if m := re.search(r"(?i)\b" + ad + EK + r"\b", s):
                fark = (wd - simdi.weekday()) % 7
                gun = simdi.date() + timedelta(days=fark)
                s = _kes(s, m)
                break

    if gun is None and saat is None:
        return None, False, _temiz(s)
    if gun is None:  # time only: today if still ahead, else tomorrow
        gun = simdi.date() if datetime.combine(simdi.date(), saat) > simdi else simdi.date() + timedelta(days=1)
    if saat is not None and datetime.combine(gun, saat) <= simdi and gun == simdi.date() and re.search(r"(?i)" + "|".join(a for a, _ in GUNLER), metin):
        gun += timedelta(days=7)  # "perşembe 10:00" said on Thursday after 10:00 -> next week
    return datetime.combine(gun, saat or time()), saat is not None, _temiz(s)


def _yil_ayarla(g: int, a: int, yil: str | None, simdi: datetime) -> date | None:
    try:
        d = date(int(yil) if yil else simdi.year, a, g)
    except ValueError:
        return None
    return d if yil or d >= simdi.date() else d.replace(year=d.year + 1)


def _temiz(s: str) -> str:
    s = DOLGU.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.-:")
    return s[:1].upper() + s[1:] if s else "(başlıksız)"
