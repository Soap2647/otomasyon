"""Read-only IMAP collection from the Gmail accounts. Newsletters filtered by rules; OTPs and links masked."""
import email
import html
import imaplib
import re
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr

from .ortam import CONFIG, log, sir

ONEMSIZ = "-category:promotions -category:social -category:forums"
_OTP_KELIME = re.compile(r"(?i)kod|code|şifre|sifre|otp|doğrulama|dogrulama|verif|pin\b|parola|password|giriş|login")
_LINK = re.compile(r"https?://\S+")


def maskele(metin: str) -> str:
    """Links -> [link]; if the text looks like a verification message, every 4-8 digit number -> [kod]."""
    metin = _LINK.sub("[link]", metin)
    return re.sub(r"\b\d{4,8}\b", "[kod]", metin) if _OTP_KELIME.search(metin) else metin
OTOMATIK = re.compile(r"(?i)no-?reply|do-?not-?reply|notification|bildirim|alert|mailer-daemon|accounts\.google")


def _baslik(v: str | None) -> str:
    return str(make_header(decode_header(v))) if v else ""


def _govde(msg: Message, n: int = 400) -> str:
    metin = ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        tur = part.get_content_type()
        if tur in ("text/plain", "text/html") and not part.get_filename():
            ham = part.get_payload(decode=True) or b""
            t = ham.decode(part.get_content_charset() or "utf-8", "replace")
            if tur == "text/html":
                t = html.unescape(re.sub(r"(?s)<(style|script).*?</\1>|<[^>]+>", " ", t))
            metin = t
            if tur == "text/plain":
                break
    return re.sub(r"\s+", " ", maskele(metin)).strip()[:n]


def _arama(m: imaplib.IMAP4_SSL, sorgu: str) -> list[bytes]:
    typ, d = m.search("UTF-8", "X-GM-RAW", f'"{sorgu}"')
    return d[0].split() if typ == "OK" else []


def topla(saat: int = 24) -> dict:
    """{'mailler': [{id, hesap, kimden, konu, ozet}], 'bulten': n, 'hatali': [hesap]}"""
    sonuc = {"mailler": [], "bulten": 0, "hatali": []}
    yas = f"newer_than:{max(1, saat // 24)}d" if saat >= 24 else f"newer_than:{saat}h"
    for hesap in CONFIG["mail"]:
        et = hesap["etiket"]
        try:
            m = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
            m.login(hesap["adres"], sir(f"GMAIL_{et}") or "")
            m.select("INBOX", readonly=True)  # never changes read/unread state
            hepsi = _arama(m, yas)
            secili = _arama(m, f"{yas} {ONEMSIZ}")
            for num in secili[-40:]:
                typ, d = m.fetch(num, "(BODY.PEEK[])")
                msg = email.message_from_bytes(d[0][1])
                if msg.get("List-Unsubscribe") or msg.get("Precedence", "").lower() in ("bulk", "list"):
                    continue  # newsletter that escaped the categories
                ad, adres = parseaddr(_baslik(msg.get("From")))
                sonuc["mailler"].append({"id": len(sonuc["mailler"]) + 1, "hesap": et, "kimden": ad or adres,
                                         "otomatik": bool(OTOMATIK.search(adres)),
                                         "konu": maskele(_baslik(msg.get("Subject")))[:150], "ozet": _govde(msg)})
            sonuc["bulten"] += len(hepsi) - len([x for x in sonuc["mailler"] if x["hesap"] == et])
            m.logout()
        except Exception as e:
            log("mail", f"{et}: {type(e).__name__} {e}")
            sonuc["hatali"].append(et)
    return sonuc
