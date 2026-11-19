"""Builds the morning briefing and the 22:30 'tomorrow' message (HTML text + button rows)."""
import json
import re
from datetime import date, datetime, timedelta
from html import escape as e

from . import durum, haber, hava, llm, mail, plan
from .ortam import CONFIG, ORTAK

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
ETIKET = ["Okul", "Staj-İş", "Fatura", "Bülten", "GDG", "Akademik", "Diğer"]


def tarih_yazi(g: date) -> str:
    return f"{g.day} {AYLAR[g.month - 1]} {GUNLER[g.weekday()]}"


SABAH_SEMA = {
    "type": "object", "required": ["yorum", "mail", "gundem"],
    "properties": {
        "yorum": {"type": "string", "maxLength": 250},
        "mail": {"type": "array", "items": {"type": "object", "required": ["id", "etiket", "cevap_gerekli", "ozet"],
                 "properties": {"id": {"type": "integer"}, "etiket": {"type": "string", "enum": ETIKET},
                                "cevap_gerekli": {"type": "boolean"}, "ozet": {"type": "string", "maxLength": 110}}}},
        "gundem": {"type": "array", "maxItems": 3, "items": {"type": "object", "required": ["id", "ozet"],
                   "properties": {"id": {"type": "integer"}, "ozet": {"type": "string", "maxLength": 120}}}},
    },
}
YORUM_SEMA = {"type": "object", "required": ["yorum"], "properties": {"yorum": {"type": "string", "maxLength": 250}}}
YARIN_ISTEM = """Mert'in yarınki planı aşağıda. Ona gece 22:30'da 1-2 cümlelik, arkadaşça ve işe yarar bir not yaz:
saat çakışması, sıkışık gün, sabah erken ders, yaklaşan son tarih, yağmur/soğuk için hazırlık vb. Planı tekrar sayma.
Kayda değer bir şey yoksa kısa bir iyi geceler yeter.

Hava: {hava}
{plan}"""
GUNDEM_SEMA ={"type": "object", "required": ["gundem"], "properties": {"gundem": SABAH_SEMA["properties"]["gundem"]}}

ISTEM = """Sen Mert'in kişisel asistanısın (Kastamonu Üniversitesi bilgisayar mühendisliği 3. sınıf; ML, sinyal işleme,
savunma sanayi ve GDG on Campus ile ilgili). Aşağıda bugünün planı, son 24 saatin mailleri ve haber başlıkları var.

YORUM: Plana, son tarihlere, havaya ve maillere bakıp Mert'e 1-2 cümlelik, arkadaşça ve gerçekten işe yarayan
bir not yaz: saat çakışması, sıkışık gün, yaklaşan son tarih, mailde bugünle ilgili bir şey, yağmur vb.
Planı tekrar sayma. Kayda değer bir şey yoksa boş bırak.
MAİL: Sadece önemli ya da cevap gerektiren mailleri seç (güvenlik uyarıları, kendi yaptığı hesap işlemleri,
otomatik bildirimler ve tanıtımlar seçilmez). Her biri için etiket, cevap gerekip gerekmediği ve Türkçe tek cümlelik
özet ("kim ne istiyor/ne oldu") yaz. Önemli mail yoksa boş liste döndür. En fazla 8 mail.
GÜNDEM: Haber adaylarından Mert için en ilgili/önemli 2-3 tanesini seç, her birine Türkçe tek cümle özet yaz.

PLAN:
{plan}

MAİLLER:
{mailler}

HABER ADAYLARI:
{haberler}"""


def _gece_satiri() -> str:
    try:
        g = json.loads((ORTAK / "gece-son.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "💻 gece işleri henüz hiç çalışmadı"
    if g.get("deneme") or datetime.now() - datetime.fromisoformat(g["zaman"]) > timedelta(hours=20):
        return "💻 dün gece çalışmadı (bilgisayar kapalıydı)"
    p = []
    if "yedek" in g:
        p.append(("✅" if g["yedek"].get("ok") else "❌") + " yedek")
    if "git" in g:
        n = sum(1 for r in g["git"]["repolar"] if r.get("durum") == "pushlandi")
        sorun = [r["repo"] for r in g["git"]["repolar"] if r.get("durum") in ("gitleaks bulgu, atlandi", "push hatasi")]
        p.append(("❌" if sorun else "✅") + f" git ({n} repo)" + (f" ⚠️ {', '.join(sorun)}" if sorun else ""))
    if "guncelle" in g:
        p.append(("✅" if g["guncelle"].get("ok") else "❌") + " güncelleme")
    if "saglik" in g:
        p.append("✅ disk" if g["saglik"].get("ok") else "❌ " + "; ".join(g["saglik"]["uyarilar"]))
    return "💾 Dün gece: " + " · ".join(p)


def sabah() -> tuple[str, list[list[dict]]]:
    bugun = date.today()
    d = durum.oku()
    s = [f"☀️ <b>{'Günaydın' if datetime.now().hour < 12 else 'Brifing'} · {tarih_yazi(bugun)}</b>"]
    try:
        hava_ = hava.ozet(0)
        s.append(f"🌡️ Kastamonu: {hava_}")
    except Exception:
        hava_ = "?"
        s.append("🌡️ ❌ hava durumu alınamadı")
    yorum_yeri = len(s)
    s += ["", "🗓️ <b>Bugün</b>"] + plan.html_bolum(bugun, d)

    m, h = mail.topla(), haber.topla(5)
    mailler = "\n".join(f"[{x['id']}] ({x['hesap']}) {x['kimden']} | {x['konu']} | {x['ozet']}" for x in m["mailler"]) or "(yok)"
    haberler = "\n".join(f"[{x['id']}] {x['kaynak']}: {x['baslik']}" for x in h)
    plan_metni = f"Hava: {hava_}\n" + plan.metin_ozet(bugun, 2, d)
    sonuc = llm.claude(ISTEM.format(plan=plan_metni, mailler=mailler, haberler=haberler), SABAH_SEMA)
    if sonuc and sonuc.get("yorum"):
        s.insert(yorum_yeri, f"💬 <i>{e(sonuc['yorum'])}</i>")

    s.append("")
    hata = f" (❌ {', '.join(m['hatali'])} okunamadı)" if m["hatali"] else ""
    if sonuc is not None:
        idx = {x["id"]: x for x in m["mailler"]}
        secili = [x for x in sonuc["mail"] if x["id"] in idx]
        cevap = [x for x in secili if x["cevap_gerekli"]]
        onemli = [x for x in secili if not x["cevap_gerekli"]]
        s.append(f"✉️ <b>Mail</b>{hata}")
        for baslik, liste in (("🔴 Cevap bekleyen", cevap), ("📌 Önemli", onemli)):
            if liste:
                s.append(baslik)
                s += [f"• [{e(x['etiket'])}] {e(idx[x['id']]['kimden'][:30])}: {e(x['ozet'])}" for x in liste]
        diger = m["bulten"] + len(m["mailler"]) - len(secili)
        s.append(f"📰 Diğer: {diger} bülten/bildirim" + ("" if secili else " · önemli mail yok"))
        gundem = sonuc["gundem"]
        onemli_var = bool(secili)
    else:  # modelless: subjects only (mail content never goes to free models)
        onemli_var = False
        insan = [x for x in m["mailler"] if not x["otomatik"]]
        s.append(f"✉️ <b>Mail</b> (özetsiz, Claude yok){hata}")
        s += [f"• ({x['hesap']}) {e(x['kimden'][:25])}: {e(x['konu'][:70])}" for x in insan[:8]]
        if len(insan) > 8:
            s.append(f"… +{len(insan) - 8} mail")
        s.append(f"📰 Diğer: {m['bulten'] + len(m['mailler']) - len(insan)} bülten/otomatik bildirim")
        g = llm.ucretsiz(f"Haber adaylarından Türkiye'deki bir bilgisayar mühendisliği öğrencisi (ML, savunma sanayi) için en önemli "
                         f"2-3 tanesini seç ve Türkçe tek cümle özetle.\n{haberler}", GUNDEM_SEMA)
        gundem = g["gundem"] if g else [{"id": x["id"], "ozet": x["baslik"]} for x in _kaynak_basina_ilk(h)]

    hidx = {x["id"]: x for x in h}
    s.append("")
    s.append("🗞️ <b>Gündem</b>")
    s += [f"• <a href=\"{e(hidx[x['id']]['link'])}\">{e(hidx[x['id']]['kaynak'])}</a>: {e(x['ozet'])}" for x in gundem if x["id"] in hidx]

    butonlar = []
    if acik := plan.yapilacaklar(bugun, d):
        s.append("")
        s.append("📝 <b>Yapılacaklar</b>")
        for x in acik:
            s.append(f"☐ {e(x['metin'])}")
            butonlar.append([{"text": f"✅ {x['metin'][:30]}", "callback_data": f"bitti:{x['id']}"}])
    s.append("")
    s.append(_gece_satiri())
    yagis = re.search(r"yağış %(\d+)", hava_)
    d = durum.oku()  # flags for the LED matrix face (matris.py)
    durum.gun(d).update(matris_mail=onemli_var, matris_yagmur=bool(yagis and int(yagis[1]) >= 60))
    durum.yaz(d)
    return "\n".join(s), butonlar


def _kaynak_basina_ilk(h: list[dict]) -> list[dict]:
    goruldu, out = set(), []
    for x in h:
        if x["kaynak"] not in goruldu and len(out) < 3:
            goruldu.add(x["kaynak"])
            out.append(x)
    return out


def _haftalik() -> list[str]:
    """Sunday add-on: per-repo commit counts, computed by the PC's nightly run (gece-son.json)."""
    s = ["", "📊 <b>Haftalık özet</b>"]
    try:
        sayilar = json.loads((ORTAK / "gece-son.json").read_text(encoding="utf-8"))["haftalik"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return s + ["• commit sayısı yok (bilgisayarın gece işi henüz yazmadı)"]
    return s + ([f"• {e(ad)}: {n} commit" for ad, n in sayilar] or ["• bu hafta commit yok"])


def yarin(vitamin: bool = False) -> tuple[str, list[list[dict]]]:
    yarin_ = date.today() + timedelta(days=1)
    d = durum.oku()
    s = [f"🌙 <b>Yarın · {tarih_yazi(yarin_)}</b>"]
    try:
        hava_ = hava.ozet(1)
        s.append(f"🌡️ {hava_}")
    except Exception:
        hava_ = "?"
    yorum = llm.claude(YARIN_ISTEM.format(hava=hava_, plan=plan.metin_ozet(yarin_, 1, d)), YORUM_SEMA, timeout=90,
                       model=CONFIG["bot"].get("model", "haiku"))
    if yorum and yorum.get("yorum"):
        s.append(f"💬 <i>{e(yorum['yorum'])}</i>")
    s += [""] + plan.html_bolum(yarin_, d)
    if acik := plan.yapilacaklar(yarin_, d):
        s.append("")
        s += [f"☐ {e(x['metin'])}" for x in acik]
    kapanis = CONFIG["gece"]["saat_hafta_sonu"] if date.today().weekday() in (4, 5) else CONFIG["gece"]["saat"]
    s.append(f"🔌 {kapanis}'da yedek, sonra kapanış")
    if date.today().weekday() == 6:
        s += _haftalik()
    s.append("")
    s.append("Eklemek ya da sormak istediğin bir şey varsa yaz yeter 💬")
    buton = [[{"text": "✅ Vitamin alındı" if vitamin else "☐ Vitamin", "callback_data": "vitamin"}]]
    return "\n".join(s), buton
