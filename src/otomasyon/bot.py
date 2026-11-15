"""Telegram bot (long polling). Answers ONLY the owner's chat_id. No irreversible actions.

  uv run python -m otomasyon.bot

Jobs: morning briefing (on start after 06:00 + daily), 22:30 'tomorrow', 23:30 one silent vitamin nudge,
reminders 15 min before timed events. Max 3 loud notifications per day; everything else silent.
"""
import asyncio
import urllib.parse
from datetime import date, datetime, time, timedelta
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from . import asistan, durum, mesaj, obsidian, plan, takvim
from .ortam import CONFIG, log, sir

C = CONFIG["bot"]
TZ = takvim.TZ
SAHIP = int(sir("TELEGRAM_CHAT_ID") or 0)


def _saat(s: str) -> time:
    h, m = map(int, s.split(":"))
    return time(h, m, tzinfo=TZ)


def _klavye(satirlar: list[list[dict]]) -> InlineKeyboardMarkup | None:
    if not satirlar:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(**b) for b in satir] for satir in satirlar])


def _sesli_mi(tur: str) -> bool:
    """Reserve one of the daily loud notifications. Returns True if this one may make a sound."""
    d = durum.oku()
    g = durum.gun(d)
    if g["sesli"] >= C["sesli_limit"]:
        log("bot", f"sesli limit doldu, sessiz: {tur}")
        return False
    g["sesli"] += 1
    durum.yaz(d)
    return True


async def gonder(app: Application, metin: str, butonlar=None, sesli: bool = False) -> int:
    m = await app.bot.send_message(SAHIP, metin[:4096], parse_mode=ParseMode.HTML, reply_markup=_klavye(butonlar or []),
                                   disable_notification=not sesli, disable_web_page_preview=True)
    return m.message_id


# ---------- scheduled messages ----------

async def sabah_gonder(app: Application, zorla: bool = False, sesli: bool = True) -> None:
    d = durum.oku()
    if durum.gun(d).get("sabah_id") and not zorla:
        return
    metin, butonlar = await asyncio.to_thread(mesaj.sabah)
    mid = await gonder(app, metin, butonlar, sesli=sesli and _sesli_mi("sabah"))
    d = durum.oku()
    durum.gun(d)["sabah_id"] = mid
    durum.yaz(d)
    obsidian.ekle("☀️ Sabah", metin)
    log("bot", "sabah brifingi gonderildi")


async def yarin_gonder(app: Application, sesli: bool = True) -> None:
    d = durum.oku()
    metin, butonlar = await asyncio.to_thread(mesaj.yarin, durum.gun(d)["vitamin"])
    mid = await gonder(app, metin, butonlar, sesli=sesli and _sesli_mi("yarin"))
    d = durum.oku()
    durum.gun(d)["yarin_id"] = mid
    durum.yaz(d)
    obsidian.ekle("🌙 Yarın", metin)


async def _job_sabah(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await sabah_gonder(ctx.application)


async def _job_yarin(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await yarin_gonder(ctx.application)


async def _job_vitamin(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    d = durum.oku()
    g = durum.gun(d)
    if g["vitamin"] or g["durtuldu"]:
        return
    g["durtuldu"] = True
    durum.yaz(d)
    await gonder(ctx.application, "💊 Vitamin? (bugün bir daha sormayacağım)",
                 [[{"text": "☐ Vitamin", "callback_data": "vitamin"}]])


_takvim_onbellek: dict = {"zaman": None, "liste": []}


async def _job_hatirlatma(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    simdi = datetime.now(TZ)
    if not _takvim_onbellek["zaman"] or simdi - _takvim_onbellek["zaman"] > timedelta(minutes=10):
        try:
            _takvim_onbellek["liste"] = await asyncio.to_thread(takvim.etkinlikler, simdi.date(), simdi.date() + timedelta(days=1))
            _takvim_onbellek["zaman"] = simdi
        except Exception as e:
            log("bot", f"takvim: {e}")
    d = durum.oku()
    adaylar = [(ev["bas"], ev["ad"]) for ev in _takvim_onbellek["liste"] if not ev["tum_gun"]]
    adaylar += [(datetime.fromisoformat(f"{x['gun']}T{x['saat']}").replace(tzinfo=TZ), x["metin"])
                for x in durum.acik(d) if x["tur"] == "etkinlik" and x["gun"] and x["saat"]]
    for bas, ad in adaylar:
        anahtar = f"{bas.isoformat()}|{ad}"
        kalan = (bas - simdi).total_seconds() / 60
        g = durum.gun(durum.oku())
        if 0 < kalan <= C["hatirlatma_dk"] and anahtar not in g["hatirlatilan"]:
            d = durum.oku()
            durum.gun(d)["hatirlatilan"].append(anahtar)
            durum.yaz(d)
            await gonder(ctx.application, f"⏰ <b>{bas:%H:%M}</b> · {ad} ({int(kalan)} dk sonra)", sesli=_sesli_mi("hatirlatma"))


# ---------- user interaction ----------

def _takvim_linki(bas: datetime, ad: str) -> str:
    bit = bas + timedelta(hours=1)
    q = {"action": "TEMPLATE", "text": ad, "dates": f"{bas:%Y%m%dT%H%M%S}/{bit:%Y%m%dT%H%M%S}", "ctz": "Europe/Istanbul",
         "authuser": C["takvim_hesap"]}
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(q)


def _is_butonlari(x: dict) -> list[dict]:
    satir = []
    if x["tur"] == "etkinlik":
        satir.append({"text": "📅 Takvime ekle", "url": _takvim_linki(datetime.fromisoformat(f"{x['gun']}T{x['saat']}"), x["metin"])})
    satir.append({"text": "🗑️ Sil", "callback_data": f"sil:{x['id']}"})
    return satir


def _uygula(d: dict, sonuc: dict) -> tuple[list[str], list[list[dict]]]:
    """Apply the model's (or the fallback's) decisions to the state. Returns card lines and button rows."""
    kartlar, butonlar = [], []
    for x in sonuc["ekle"]:
        if not x["metin"].strip():
            continue
        tur = x["tur"] if x["tur"] != "etkinlik" or (x["gun"] and x["saat"]) else "yapilacak"
        yeni = durum.ekle(d, tur, x["metin"].strip(), x["gun"], x["saat"] if tur == "etkinlik" else None)
        kartlar.append(plan.kart(yeni))
        butonlar.append(_is_butonlari(yeni))
    for g in sonuc["guncelle"]:
        if x := durum.bul(d, g["id"]):
            x.update(tur=g["tur"], metin=g["metin"] or x["metin"], gun=g["gun"] or None,
                     saat=(g["saat"] or None) if g["tur"] == "etkinlik" else None)
            kartlar.append("✏️ " + plan.kart(x))
            butonlar.append(_is_butonlari(x))
    for alan, isaret in (("tamamla", "✅"), ("iptal", "🗑️")):
        for i in sonuc[alan]:
            if x := durum.bul(d, i):
                x["bitti" if alan == "tamamla" else "iptal"] = True
                kartlar.append(f"{isaret} <s>{escape(x['metin'])}</s>")
                butonlar.append([{"text": "↩️ Geri al", "callback_data": f"geri:{x['id']}"}])
    return kartlar, butonlar


async def not_al(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    metin = update.message.text.strip()
    await ctx.bot.send_chat_action(SAHIP, ChatAction.TYPING)
    sonuc = await asyncio.to_thread(asistan.anla, metin) or asistan.kural_ile(metin)
    d = durum.oku()
    kartlar, butonlar = _uygula(d, sonuc)
    durum.yaz(d)
    cevap = "\n".join(([escape(sonuc["yanit"])] if sonuc["yanit"] else []) + ([""] + kartlar if kartlar else []))
    await update.message.reply_html(cevap or "👍", reply_markup=_klavye(butonlar), disable_notification=True,
                                    disable_web_page_preview=True)
    if kartlar:
        obsidian.ekle("📝 Not", "\n".join(kartlar))


async def buton(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q.from_user.id != SAHIP:
        return
    veri = q.data or ""
    d = durum.oku()
    if veri == "vitamin":
        g = durum.gun(d)
        g["vitamin"] = not g["vitamin"]
        durum.yaz(d)
        await q.answer("Vitamin ✅" if g["vitamin"] else "Geri alındı")
        await q.edit_message_reply_markup(_klavye([[{"text": "✅ Vitamin alındı" if g["vitamin"] else "☐ Vitamin", "callback_data": "vitamin"}]]))
        return
    eylem, _, i = veri.partition(":")
    x = durum.bul(d, int(i)) if i.isdigit() and eylem in ("bitti", "sil", "geri") else None
    if x is None:
        await q.answer("Bu eski bir mesaj, /liste'den bak")
        return
    if eylem == "bitti":
        x["bitti"] = True
        metin = q.message.text_html.replace(f"☐ {escape(x['metin'])}", f"✅ {escape(x['metin'])}", 1)
        kalan = [r for r in q.message.reply_markup.inline_keyboard if r[0].callback_data != veri]
        await q.edit_message_text(metin, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kalan),
                                  disable_web_page_preview=True)
        await q.answer("Tamamlandı ✅")
    else:  # sil / geri: flip the cancelled flag on this card's row, reversible
        sil = eylem == "sil"
        x["iptal"] = sil
        if not sil:
            x["bitti"] = False
        yeni = [[{"text": "↩️ Geri al", "callback_data": f"geri:{x['id']}"}] if sil else _is_butonlari(x)]
        satirlar = [[b.to_dict() for b in r] for r in q.message.reply_markup.inline_keyboard]
        satirlar = [yeni[0] if any(b.get("callback_data") == veri for b in r) else r for r in satirlar]
        await q.edit_message_reply_markup(_klavye(satirlar))
        await q.answer("Silindi" if sil else "Geri alındı")
    durum.yaz(d)


async def komut_sabah(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("☀️ Hazırlıyorum (mailler + özet ~1 dk)...", disable_notification=True)
    await sabah_gonder(ctx.application, zorla=True, sesli=False)


async def komut_yarin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await yarin_gonder(ctx.application, sesli=False)


async def komut_liste(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    d = durum.oku()
    bugun = date.today().isoformat()
    acik = [x for x in durum.acik(d) if not (x["tur"] == "etkinlik" and x["gun"] < bugun)]  # past events drop off
    sira = {"etkinlik": 0, "son": 1, "yapilacak": 2}
    acik.sort(key=lambda x: (sira[x["tur"]], x["gun"] or "9999", x["saat"] or ""))
    satirlar = [plan.kart(x) for x in acik] or ["Açık iş yok 🎉"]
    butonlar = [[{"text": f"✅ {x['metin'][:28]}", "callback_data": f"bitti:{x['id']}"}] for x in acik if x["tur"] != "etkinlik"]
    metin = "📋 <b>Açık işler</b>\n" + "\n".join(f"☐ {s}" if not s.startswith("📌") else s for s in satirlar)
    await update.message.reply_html(metin, reply_markup=_klavye(butonlar), disable_notification=True)


async def komut_yardim(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "<b>Jarvis</b>: bana normal konuşur gibi yaz.\n"
        "• <i>cuma 14.00 U Fest'e katıl</i> → etkinlik, 15 dk önce hatırlatırım\n"
        "• <i>Genç 2030 formunu 9 kasıma kadar doldur</i> → son tarih, geri sayım\n"
        "• <i>ekmek al</i> → yapılacak\n"
        "• <i>ekmeği aldım</i>, <i>U Fest iptal oldu</i>, <i>onu 15'e al</i> → listeyi günceller\n"
        "• <i>yarın ne var?</i>, <i>bu hafta boş günüm hangisi?</i> → plana bakıp cevaplarım\n"
        "/sabah · /yarin · /liste", disable_notification=True)


async def _baslangic(app: Application) -> None:
    jq = app.job_queue
    jq.run_daily(_job_sabah, _saat(CONFIG["sabah"]["saat"]), name="sabah")
    jq.run_daily(_job_yarin, _saat(C["yarin_saat"]), name="yarin")
    jq.run_daily(_job_vitamin, _saat(C["vitamin_durt"]), name="vitamin")
    jq.run_repeating(_job_hatirlatma, interval=60, first=10, name="hatirlatma")
    simdi = datetime.now(TZ)
    if _saat(CONFIG["sabah"]["en_erken"]).replace(tzinfo=None) <= simdi.time() < time(18, 0):
        jq.run_once(_job_sabah, 30, name="sabah-acilis")  # first logon of the day (skipped if already sent)
    log("bot", "bot basladi")


def main() -> None:
    import logging
    from .ortam import STATE
    logging.basicConfig(filename=STATE / "bot.log", level=logging.WARNING, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not SAHIP or not sir("TELEGRAM_TOKEN"):
        raise SystemExit(".env'de TELEGRAM_TOKEN / TELEGRAM_CHAT_ID yok")
    app = Application.builder().token(sir("TELEGRAM_TOKEN")).post_init(_baslangic).build()
    sahip = filters.Chat(chat_id=SAHIP)
    app.add_handler(CommandHandler("sabah", komut_sabah, filters=sahip))
    app.add_handler(CommandHandler("yarin", komut_yarin, filters=sahip))
    app.add_handler(CommandHandler("liste", komut_liste, filters=sahip))
    app.add_handler(CommandHandler(["yardim", "start", "help"], komut_yardim, filters=sahip))
    app.add_handler(MessageHandler(sahip & filters.TEXT & ~filters.COMMAND, not_al))
    app.add_handler(CallbackQueryHandler(buton))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
