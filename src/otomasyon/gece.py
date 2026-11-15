"""Nightly runner. Default is a DRY RUN (changes nothing). Real run needs --uygula.

  uv run python -m otomasyon.gece                      # dry run, all steps
  uv run python -m otomasyon.gece --sadece git,saglik  # dry run, chosen steps
  uv run python -m otomasyon.gece --uygula             # real run (used by Task Scheduler)
"""
import argparse
import json
from datetime import date

from . import bakim, gitwip, kapanis, yedek
from .ortam import STATE, kaydet, log

ADIMLAR = ["yedek", "ikinci", "git", "guncelle", "saglik", "kapanis"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="gercekten calistir (yoksa deneme)")
    ap.add_argument("--sadece", default=",".join(ADIMLAR))
    a = ap.parse_args()
    deneme, secili = not a.uygula, a.sadece.split(",")
    log("gece", f"===== basladi ({'DENEME' if deneme else 'GERCEK'}) adimlar={secili}")
    s: dict = {"deneme": deneme}

    if "yedek" in secili:
        s["yedek"] = yedek.yedekle(deneme)
    if "ikinci" in secili and date.today().weekday() == 6:  # Pazar
        s["ikinci_kopya"] = yedek.ikinci_kopya(deneme)
    if "git" in secili:
        s["git"] = gitwip.calistir_hepsi(deneme)
    if "guncelle" in secili:
        s["guncelle"] = bakim.guncelle(deneme)
    if "saglik" in secili:
        s["saglik"] = bakim.saglik()
    kaydet("gece-son", s)  # morning briefing reads this

    if "kapanis" in secili:
        if s.get("yedek", {}).get("ok") is False:
            s["kapanis"] = {"durum": "yedek hatali, kapanmadi", "kapandi": False}
            log("kapanis", "yedek hatali -> kapanmiyor")
        else:
            s["kapanis"] = kapanis.kapat(deneme)
        kaydet("gece-son", s)
    log("gece", "===== bitti")
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"\nSonuc dosyasi: {STATE / 'gece-son.json'}")


if __name__ == "__main__":
    main()
