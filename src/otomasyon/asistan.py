"""Understands free-text Telegram messages with Claude: add/complete/cancel/update items, or answer questions.

Context sent to the model: now, the next 8 days' plan (courses + calendar + items), open items with ids, weather,
and the last few exchanges (so "onu 15'e al" works). Returns None if Claude is unavailable -> rule-based fallback.
"""
from datetime import date, datetime

from . import durum, hava, llm, plan
from .mesaj import tarih_yazi
from .ortam import CONFIG

MODEL = CONFIG["bot"].get("model", "haiku")
GECMIS: list[str] = []   # last exchanges, in-process only

SISTEM = """Sen Jarvis'sin: Mert'in Telegram'daki kişisel asistanı (Kastamonu Üniversitesi bilgisayar mühendisliği
3. sınıf öğrencisi). Türkçe, samimi ve kısa konuşursun; arkadaş gibi ama abartmadan, en fazla bir emoji.
Sadece sana verilen bağlama dayanırsın, uydurmazsın. Mail gönderemez, Google Takvim'e kendin yazamazsın
(etkinliklerin altında "Takvime ekle" butonu çıkar). Cevabı istenen JSON şemasına uygun döndür."""

SEMA = {
    "type": "object", "required": ["ekle", "tamamla", "iptal", "guncelle", "yanit"],
    "properties": {
        "ekle": {"type": "array", "items": {
            "type": "object", "required": ["tur", "metin", "gun", "saat"],
            "properties": {"tur": {"type": "string", "enum": ["etkinlik", "son", "yapilacak"]},
                           "metin": {"type": "string", "maxLength": 80},
                           "gun": {"type": "string", "description": "YYYY-MM-DD ya da boş"},
                           "saat": {"type": "string", "description": "HH:MM ya da boş"}}}},
        "tamamla": {"type": "array", "items": {"type": "integer"}},
        "iptal": {"type": "array", "items": {"type": "integer"}},
        "guncelle": {"type": "array", "items": {
            "type": "object", "required": ["id", "tur", "metin", "gun", "saat"],
            "properties": {"id": {"type": "integer"}, "tur": {"type": "string", "enum": ["etkinlik", "son", "yapilacak"]},
                           "metin": {"type": "string"}, "gun": {"type": "string"}, "saat": {"type": "string"}}}},
        "yanit": {"type": "string", "maxLength": 500},
    },
}

ISTEM = """ŞU AN: {simdi}
HAVA (günlük tahmin, anlık değil): bugün {hava0} · yarın {hava1}

PLAN (dersler, Google Takvim, 📌 = botta kayıtlı etkinlik):
{plan}

SON KONUŞMA:
{gecmis}

MERT'İN YENİ MESAJI: {mesaj}

Kurallar:
- Mesaj bir iş/etkinlik/hatırlatma ise "ekle"ye yaz. Tür: belirli saati olan → etkinlik; bir tarihe kadar
  yapılması gereken (form, ödev, başvuru, ödeme) → son; diğerleri → yapilacak (gun sadece "o gün yapılacak"sa dolu).
  Göreli tarihleri ŞU AN'a göre çöz. "metin": kısa, düzgün yazılmış başlık; tarih/saat ifadelerini çıkar,
  kişi/yer bilgisini koru.
- "X'i yaptım/aldım/hallettim" → ilgili açık işin id'si "tamamla"ya. "X iptal oldu / vazgeçtim" → "iptal"e.
  "Onu 15'e al" gibi değişiklik → "guncelle" (id'nin tüm alanlarıyla).
- Soru ise (ör. "yarın ne var", "bu hafta boş günüm hangisi") plana bakıp cevapla; hiçbir listeye bir şey yazma.
- "yanit": Mert'e düz metin kısa cevap. Eklenen işin tarih/saatini tekrarlama (onları ayrıca kart olarak
  gösteriyorum). Gerçekten işe yarıyorsa tek bir şey ekle: çakışma (aynı saatte ders/etkinlik), yaklaşan son
  tarih, yağmur vb. Gereksiz laf yok.
- Selam/sohbet mesajına kısa ve doğal karşılık ver; sorulmadıkça hava ya da plan anlatma."""


def kural_ile(mesaj: str) -> dict:
    """Fallback without a model: rule-based date parsing, always 'add'."""
    from .tarih import SON_TARIH, ayristir
    dt, saatli, baslik = ayristir(mesaj, datetime.now())
    tur = "etkinlik" if saatli else "son" if dt and SON_TARIH.search(mesaj) else "yapilacak"
    return {"ekle": [{"tur": tur, "metin": baslik, "gun": dt.date().isoformat() if dt else "",
                      "saat": f"{dt:%H:%M}" if saatli else ""}],
            "tamamla": [], "iptal": [], "guncelle": [], "yanit": "Not aldım (Claude'a ulaşamadım, kuralla ayrıştırdım)."}


def _hava(g: int) -> str:
    try:
        return hava.ozet(g)
    except Exception:
        return "?"


def anla(mesaj: str) -> dict | None:
    simdi = datetime.now()
    d = durum.oku()
    istem = ISTEM.format(simdi=f"{tarih_yazi(simdi.date())} {simdi:%H:%M} ({simdi.date().isoformat()})",
                         hava0=_hava(0), hava1=_hava(1), plan=plan.metin_ozet(date.today(), 8, d),
                         gecmis="\n".join(GECMIS[-6:]) or "(yok)", mesaj=mesaj)
    sonuc = llm.claude(istem, SEMA, timeout=90, model=MODEL, sistem=SISTEM)
    if sonuc is not None:
        GECMIS.extend([f"Mert: {mesaj}", f"Jarvis: {sonuc['yanit']}"])
    return sonuc
