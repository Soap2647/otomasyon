"""Shows which secrets exist in .env (never their values). Secrets are added by editing .env by hand.

  uv run python -m otomasyon.secrets
"""
from .ortam import CONFIG, KOK, sir

GEREKEN = ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY", "NVIDIA_API_KEY", "OPENROUTER_API_KEY"] + [
    "GMAIL_" + m["etiket"] for m in CONFIG["mail"]
]

if __name__ == "__main__":
    print(f".env: {KOK / '.env'}")
    for ad in GEREKEN:
        print(f"{'VAR' if sir(ad) else 'YOK'}  {ad}")
