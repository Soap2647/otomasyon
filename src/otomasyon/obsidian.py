"""Append bot messages to the Obsidian daily note (05 Gunluk/YYYY-MM-DD.md), created from the template if missing."""
import html
import re
from datetime import date
from pathlib import Path

from .mesaj import AYLAR, GUNLER
from .ortam import CONFIG, log

C = CONFIG["bot"]


def _not(g: date) -> Path:
    yol = Path(C["gunluk"]) / f"{g.isoformat()}.md"
    if not yol.exists():
        sablon = Path(C["gunluk_sablon"]).read_text(encoding="utf-8")
        sablon = sablon.replace("{{date:YYYY-MM-DD}}", g.isoformat()).replace(
            "{{date:DD MMMM YYYY, dddd}}", f"{g.day:02d} {AYLAR[g.month - 1]} {g.year}, {GUNLER[g.weekday()]}")
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(sablon, encoding="utf-8")
    return yol


def ekle(baslik: str, html_metin: str, g: date | None = None) -> None:
    try:
        duz = re.sub(r"<a href=\"([^\"]+)\">([^<]+)</a>", r"[\2](\1)", html_metin)
        duz = re.sub(r"</?b>", "**", duz)
        duz = re.sub(r"</?i>", "_", duz)
        duz = html.unescape(re.sub(r"<[^>]+>", "", duz))
        yol = _not(g or date.today())
        metin = yol.read_text(encoding="utf-8")
        if "## Jarvis" not in metin:
            metin = metin.rstrip() + "\n\n## Jarvis\n"
        yol.write_text(metin.rstrip() + f"\n\n### {baslik}\n{duz}\n", encoding="utf-8")
    except Exception as e:
        log("obsidian", f"{type(e).__name__}: {e}")
