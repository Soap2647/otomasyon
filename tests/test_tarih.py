from datetime import datetime

import pytest

from otomasyon.tarih import ayristir

SIMDI = datetime(2026, 11, 5, 12, 0)  # Thursday 12:00


@pytest.mark.parametrize("metin, beklenen_dt, saatli, baslik", [
    ("cuma 14:00 diş randevusu", datetime(2026, 11, 6, 14, 0), True, "Diş randevusu"),
    ("yarın 15:00 hocaya mail at", datetime(2026, 11, 6, 15, 0), True, "Hocaya mail at"),
    ("yarın annemi ara", datetime(2026, 11, 6, 0, 0), False, "Annemi ara"),
    ("süt al", None, False, "Süt al"),
    ("12 kasım 10:30 vize", datetime(2026, 11, 12, 10, 30), True, "Vize"),
    ("2 saat sonra çamaşırı as", datetime(2026, 11, 5, 14, 0), True, "Çamaşırı as"),
    ("30 dk sonra fırını kapat", datetime(2026, 11, 5, 12, 30), True, "Fırını kapat"),
    ("akşam 7 GDG toplantısı", datetime(2026, 11, 5, 19, 0), True, "GDG toplantısı"),
    ("cumartesi'ye sinema", datetime(2026, 11, 7, 0, 0), False, "Sinema"),
    ("pazartesi saat 9'da lab", datetime(2026, 11, 9, 9, 0), True, "Lab"),
    ("perşembe 10:00 toplantı", datetime(2026, 11, 12, 10, 0), True, "Toplantı"),  # Thursday, 10:00 passed -> next week
    ("14'te kargo gelecek", datetime(2026, 11, 5, 14, 0), True, "Kargo gelecek"),
    ("09:00 dişçi", datetime(2026, 11, 6, 9, 0), True, "Dişçi"),            # past today -> tomorrow
    ("12.11 proje teslimi", datetime(2026, 11, 12, 0, 0), False, "Proje teslimi"),
    ("3 ocak kayıt yenileme", datetime(2027, 1, 3, 0, 0), False, "Kayıt yenileme"),
    ("öğlen yemek", datetime(2026, 11, 6, 12, 0), True, "Yemek"),           # 12:00 exactly now -> tomorrow
    ("U Feste katıl 6 kasım 14.00", datetime(2026, 11, 6, 14, 0), True, "U Feste katıl"),
    ("cuma 9.30 lab", datetime(2026, 11, 6, 9, 30), True, "Lab"),
    ("Genç 2030 formunu 9 kasıma kadar doldur", datetime(2026, 11, 9, 0, 0), False, "Genç 2030 formunu doldur"),
])
def test_ayristir(metin, beklenen_dt, saatli, baslik):
    dt, s, b = ayristir(metin, SIMDI)
    assert (dt, s, b) == (beklenen_dt, saatli, baslik)
