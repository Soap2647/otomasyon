"""Kahya's face on the UNO Q 8x13 LED matrix.

Every 30 s a mood is picked from the bot state (priority: ders > vitamin > mail > yagmur > uyku > bosta; "mutlu" for a
few seconds after the vitamin button), and its animation is streamed to the kahya-yuz App's sketch ("draw", 104 bytes
0..255) over the Arduino router socket. Does nothing where there is no socket (the PC).
"""
import random
import re
import threading
import time
from datetime import date, datetime

from . import durum, plan
from .ortam import CONFIG, log

SOKET = "/var/run/arduino-router.sock"
SECIM_SN = 30
E = "." * 13


def _yuz(g1: str, g2: str, a1: str, a2: str) -> list[str]:
    return [E, E, g1, g2, E, a1, a2, E]


ACIK = _yuz("...##...##...", "...##...##...", "....#...#....", ".....###.....")
KIRP = _yuz(E, "...##...##...", "....#...#....", ".....###.....")
MUTLU = _yuz("...#.....#...", "..#.#...#.#..", "...#.....#...", "....#####....")
HAP = [E, "....#####....", "...#..#..#...", "..#...#...#..", "..#...#...#..", "...#..#..#...", "....#####....", E]
ZARF = [E, "..#########..", "..##.....##..", "..#.#...#.#..", "..#..#.#..#..", "..#...#...#..", "..#########..", E]
BOS = [E] * 8
Z = [["..........###", "...........#.", "..........###"], [".........###.", "..........#..", ".........###."]]
RAKAM = {0: ["###", "#.#", "#.#", "#.#", "###"], 1: [".#.", "##.", ".#.", ".#.", "###"], 2: ["###", "..#", "###", "#..", "###"],
         3: ["###", "..#", ".##", "..#", "###"], 4: ["#.#", "#.#", "###", "..#", "..#"], 5: ["###", "#..", "###", "..#", "###"],
         6: ["###", "#..", "###", "#.#", "###"], 7: ["###", "..#", "..#", "..#", "..#"], 8: ["###", "#.#", "###", "#.#", "###"],
         9: ["###", "#.#", "###", "..#", "###"]}


def _uyku(t: int) -> list[str]:
    return Z[t % 2] + [".." + "###" + "..." + "###" + "..", E, E, ".....##......", E]


def _sayi(n: int) -> list[str]:
    """Minutes left (0..15) in big digits, with a shrinking bar on the bottom row."""
    a, b = RAKAM[n // 10], RAKAM[n % 10]
    dolu = round(n / 15 * 13)
    return [E] + [f"...{a[r]}.{b[r]}..." for r in range(5)] + [E, "#" * dolu + "." * (13 - dolu)]


_damla: list[list[int]] = []


def _yagmur(_t: int) -> list[str]:
    global _damla
    if random.random() < 0.7:
        _damla.append([0, random.randrange(13)])
    _damla = [[r + 1, c] for r, c in _damla if r + 1 < 8]
    f = [["."] * 13 for _ in range(8)]
    for r, c in _damla:
        f[r][c] = "#"
    return ["".join(r) for r in f]


# mood -> (tick ms, brightness 0..1, frame(t))
DURUMLAR = {
    "bosta": (250, 1.0, lambda t: KIRP if t % 16 == 0 else ACIK),
    "mutlu": (400, 1.0, lambda t: MUTLU if t % 2 else ACIK),
    "vitamin": (700, 1.0, lambda t: HAP if t % 2 else BOS),
    "mail": (500, 1.0, lambda t: BOS if t % 4 == 3 else ZARF),
    "yagmur": (150, 1.0, _yagmur),
    "uyku": (900, 0.2, _uyku),
}

_mutlu_bitis = 0.0
_cizelge: tuple[float, list[tuple[str, str]]] = (0.0, [])


def mutlu(sn: float = 6) -> None:
    """Short happy face (vitamin marked)."""
    global _mutlu_bitis
    _mutlu_bitis = time.monotonic() + sn


def _bugunku_saatler(d: dict) -> list[str]:
    """Today's HH:MM start times (courses, calendar, bot events); the calendar is fetched at most every 5 min."""
    global _cizelge
    if time.monotonic() - _cizelge[0] > 300:
        _cizelge = (time.monotonic(), plan.zaman_cizelgesi(date.today(), d))
    return [z for z, _ in _cizelge[1] if re.fullmatch(r"\d\d:\d\d", z)]


def sec(simdi: datetime, d: dict) -> tuple[str, int | None]:
    """(mood, minutes left for 'ders')."""
    if time.monotonic() < _mutlu_bitis:
        return "mutlu", None
    g, saat = durum.gun(d), simdi.strftime("%H:%M")
    dakikalar = [(int(z[:2]) * 60 + int(z[3:])) - (simdi.hour * 60 + simdi.minute) for z in _bugunku_saatler(d)]
    if yakin := [k for k in dakikalar if 0 < k <= 15]:
        return "ders", min(yakin)
    if saat >= CONFIG["bot"]["yarin_saat"] and not g["vitamin"]:
        return "vitamin", None
    if g.get("matris_mail") and simdi.hour < 12:
        return "mail", None
    if g.get("matris_yagmur") and 6 <= simdi.hour < 10:
        return "yagmur", None
    if CONFIG["gece"]["saat"] <= saat < "07:00":
        return "uyku", None
    return "bosta", None


def _bayt(kare: list[str], parlak: float) -> bytes:
    acik = round(255 * parlak)
    return bytes(acik if c == "#" else 0 for r in kare for c in r)


def _dongu() -> None:
    from arduino.router_bridge import Bridge
    kopru, ad, dk, t, sonraki, son_hata = None, "bosta", None, 0, 0.0, ""
    while True:
        try:
            if kopru is None:
                kopru = Bridge(f"unix://{SOKET}")
                if not kopru.connect(timeout=5):
                    raise ConnectionError("router'a baglanilamadi")
            if time.monotonic() >= sonraki or (ad != "mutlu" and time.monotonic() < _mutlu_bitis):
                yeni, dk = sec(datetime.now(), durum.oku())
                if yeni != ad:
                    ad, t = yeni, 0
                sonraki = time.monotonic() + (1 if ad == "mutlu" else SECIM_SN)
            if ad == "ders":
                ms, parlak, kare = 1000, 1.0, _sayi(dk or 0)
            else:
                ms, parlak, fn = DURUMLAR[ad]
                kare = fn(t)
            kopru.call("draw", _bayt(kare, parlak), timeout=3)
            t += 1
            time.sleep(ms / 1000)
        except Exception as e:  # router/sketch restarting, calendar down...: retry quietly
            if (hata := f"{type(e).__name__}: {e}") != son_hata:  # log each distinct error once, not every 30 s
                log("matris", hata)
                son_hata = hata
            if kopru is not None:
                kopru.disconnect()
                kopru = None
            time.sleep(30)


def baslat() -> None:
    """Start the face loop in a daemon thread if this machine has the Arduino router (UNO Q)."""
    from pathlib import Path
    if Path(SOKET).exists():
        threading.Thread(target=_dongu, name="matris", daemon=True).start()
        log("matris", "basladi")
