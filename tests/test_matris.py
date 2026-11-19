from datetime import date, datetime

import pytest

from otomasyon import matris

GUN = date(2026, 11, 19)


@pytest.fixture
def ders_0930(monkeypatch):
    monkeypatch.setattr(matris, "_bugunku_saatler", lambda d: ["09:30", "14:30"])
    monkeypatch.setattr(matris, "_mutlu_bitis", 0.0)


def durum(**gun):
    return {"gun": {GUN.isoformat(): {"sesli": 0, "vitamin": False, "durtuldu": False, "hatirlatilan": [], **gun}}, "isler": []}


def sec(saat, d, monkeypatch):
    monkeypatch.setattr(matris.durum, "date", type("D", (), {"today": staticmethod(lambda: GUN)}))
    h, m = map(int, saat.split(":"))
    return matris.sec(datetime(GUN.year, GUN.month, GUN.day, h, m), d)


@pytest.mark.parametrize("saat,beklenen", [
    ("09:20", ("ders", 10)), ("09:30", ("bosta", None)), ("14:16", ("ders", 14)),
    ("08:00", ("bosta", None)), ("00:45", ("uyku", None)), ("07:00", ("bosta", None)), ("22:45", ("vitamin", None)),
])
def test_saate_gore(saat, beklenen, ders_0930, monkeypatch):
    assert sec(saat, durum(), monkeypatch) == beklenen


def test_oncelik(ders_0930, monkeypatch):
    d = durum(matris_mail=True, matris_yagmur=True)
    assert sec("09:20", d, monkeypatch)[0] == "ders"      # ders beats mail/rain
    assert sec("08:00", d, monkeypatch)[0] == "mail"      # mail beats rain
    assert sec("12:30", d, monkeypatch)[0] == "bosta"     # mail only before noon
    assert sec("08:00", durum(matris_yagmur=True), monkeypatch)[0] == "yagmur"
    assert sec("22:45", durum(vitamin=True), monkeypatch)[0] == "bosta"


def test_mutlu_hepsini_ezer(ders_0930, monkeypatch):
    matris.mutlu()
    assert sec("09:20", durum(), monkeypatch)[0] == "mutlu"


def test_kareler_8x13():
    kareler = [matris._sayi(n) for n in range(16)] + [matris._uyku(t) for t in range(2)] + [matris._yagmur(t) for t in range(10)]
    kareler += [fn(t) for _, _, fn in matris.DURUMLAR.values() for t in range(4)]
    for k in kareler:
        assert len(k) == 8 and all(len(r) == 13 for r in k)
    assert len(matris._bayt(matris.ACIK, 0.2)) == 104
