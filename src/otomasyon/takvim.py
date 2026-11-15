"""Google Calendar via secret iCal URL (read-only) + Turkish public holidays. Times converted to Istanbul."""
import time as _time
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

from .ortam import sir

TZ = ZoneInfo("Europe/Istanbul")
TATIL_URL = "https://calendar.google.com/calendar/ical/tr.turkish%23holiday%40group.v.calendar.google.com/public/basic.ics"


_ONBELLEK: dict[str, tuple[float, icalendar.Calendar]] = {}


def _oku(url: str) -> icalendar.Calendar:
    """Downloaded feed, cached 10 min (the assistant reads a week of days per message)."""
    if (k := _ONBELLEK.get(url)) and _time.time() - k[0] < 600:
        return k[1]
    cal = icalendar.Calendar.from_ical(urllib.request.urlopen(url, timeout=30).read())
    _ONBELLEK[url] = (_time.time(), cal)
    return cal


def etkinlikler(bas: date, bit: date) -> list[dict]:
    """Events between [bas, bit] (inclusive), recurring expanded: {bas, bit, ad, tum_gun, yer}."""
    url = sir("TAKVIM_ICAL")
    if not url:
        return []
    out = []
    for e in recurring_ical_events.of(_oku(url)).between(bas, bit + timedelta(days=1)):
        b, s = e["DTSTART"].dt, e.get("DTEND", e["DTSTART"]).dt
        tum_gun = not isinstance(b, datetime)
        if not tum_gun:
            b = (b if b.tzinfo else b.replace(tzinfo=TZ)).astimezone(TZ)  # e.g. Dubai -> Istanbul
            s = (s if s.tzinfo else s.replace(tzinfo=TZ)).astimezone(TZ)
        out.append({"bas": b, "bit": s, "ad": str(e.get("SUMMARY", "(başlıksız)")), "tum_gun": tum_gun,
                    "yer": str(e.get("LOCATION", "") or "")})
    return sorted(out, key=lambda x: (not x["tum_gun"], x["bas"] if not x["tum_gun"] else datetime.combine(x["bas"], time(), TZ)))


def tatil(gun: date) -> str | None:
    try:
        for e in recurring_ical_events.of(_oku(TATIL_URL)).at(gun):
            return str(e.get("SUMMARY"))
    except Exception:
        return None
    return None


def satirlar(gun: date) -> list[str]:
    return [f"{'Tüm gün' if e['tum_gun'] else e['bas'].strftime('%H:%M')} {e['ad']}" for e in etkinlikler(gun, gun)]
