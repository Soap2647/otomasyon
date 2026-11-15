"""RSS headlines (public data)."""
import socket

import feedparser

from .ortam import CONFIG, log


def topla(adet: int = 5) -> list[dict]:
    """Candidate headlines: {id, kaynak, baslik, link}."""
    socket.setdefaulttimeout(20)
    out = []
    for k in CONFIG["haber"]["kaynak"]:
        f = feedparser.parse(k["url"], agent="Mozilla/5.0 otomasyon")
        if not f.entries:
            log("haber", f"{k['ad']}: bos ({f.get('bozo_exception')})")
        for e in f.entries[:adet]:
            out.append({"id": len(out) + 1, "kaynak": k["ad"], "baslik": e.get("title", "").strip(), "link": e.get("link", "")})
    return out
