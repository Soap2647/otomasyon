"""Model calls. Claude (subscription, `claude -p`) for everything; free models ONLY for public data.

Every call is bound to a JSON schema; callers get a dict or None (-> modelless fallback).
"""
import json
import shutil
import subprocess
import tempfile
import urllib.request

from .ortam import CONFIG, log, sir

C = CONFIG["sabah"]
CLAUDE = shutil.which("claude")
SISTEM = ("Sen Mert'in kişisel asistanısın. Türkçe, kısa ve net yaz. Uydurma bilgi ekleme; "
          "sadece verilen veriye dayan ve cevabı istenen JSON şemasına uygun döndür.")


def claude(istem: str, sema: dict, timeout: int = 300, model: str | None = None, sistem: str = SISTEM) -> dict | None:
    if not CLAUDE:
        return None
    # Lean mode: own system prompt, no tools/MCP/plugins/user settings -> ~1.4k tokens instead of ~109k per call.
    # (--bare would be leaner but ignores the subscription login.)
    cmd = [CLAUDE, "-p", "--model", model or C["claude_model"], "--output-format", "json", "--json-schema", json.dumps(sema),
           "--tools", "", "--no-session-persistence", "--system-prompt", sistem,
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", ""]
    try:
        with tempfile.TemporaryDirectory() as bos:  # empty cwd: no project CLAUDE.md pulled in
            r = subprocess.run(cmd, input=istem, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=bos)
        j = json.loads(r.stdout)
        if j.get("is_error") or not j.get("structured_output"):
            log("llm", f"claude: {str(j.get('result'))[:120]}")
            return None
        u = j.get("usage", {})
        log("llm", f"claude ok: in={u.get('input_tokens')} cache={u.get('cache_read_input_tokens')} out={u.get('output_tokens')}")
        return j["structured_output"]
    except Exception as e:
        log("llm", f"claude hata: {type(e).__name__} {e}")
        return None


def _post(url: str, govde: dict, basliklar: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(govde).encode(), headers={"Content-Type": "application/json", **basliklar})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _openrouter_free() -> list[str]:
    d = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20))["data"]
    return [m["id"] for m in d if m["id"].endswith(":free") and "safety" not in m["id"]][:4]


def _json_ayikla(metin: str) -> dict:
    metin = metin.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(metin[metin.find("{"): metin.rfind("}") + 1])


def ucretsiz(istem: str, sema: dict) -> dict | None:
    """Free-model chain. PUBLIC DATA ONLY (news, job ads) - never mail content."""
    istem = f"{istem}\n\nSADECE bu JSON şemasına uyan geçerli JSON döndür, başka hiçbir şey yazma:\n{json.dumps(sema, ensure_ascii=False)}"
    for aday in C["yedek_modeller"]:
        saglayici, model = aday.split(":", 1)
        modeller = _openrouter_free() if model == "auto-free" else [model]
        for m in modeller:
            try:
                if saglayici == "gemini":
                    d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              {"contents": [{"parts": [{"text": istem}]}], "generationConfig": {"responseMimeType": "application/json"}},
                              {"x-goog-api-key": sir("GEMINI_API_KEY") or ""}, 60)
                    metin = d["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    url, anahtar = {"openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
                                    "nvidia": ("https://integrate.api.nvidia.com/v1/chat/completions", "NVIDIA_API_KEY")}[saglayici]
                    d = _post(url, {"model": m, "messages": [{"role": "user", "content": istem}], "max_tokens": 1500},
                              {"Authorization": f"Bearer {sir(anahtar)}"}, 30)
                    metin = d["choices"][0]["message"]["content"]
                sonuc = _json_ayikla(metin)
                log("llm", f"yedek model ok: {saglayici}:{m}")
                return sonuc
            except Exception as e:
                log("llm", f"yedek {saglayici}:{m} -> {type(e).__name__} {getattr(e, 'code', '')}")
    return None
