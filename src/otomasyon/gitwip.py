"""Push uncommitted work to a wip branch WITHOUT touching the working tree, index or current branch.

Snapshot is built in a temporary index (GIT_INDEX_FILE), committed with commit-tree on top of HEAD,
scanned with gitleaks, then force-pushed to refs/heads/<branch>. Local refs are not changed.
"""
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from .ortam import CONFIG, calistir, log

C = CONFIG["git"]
GITLEAKS = shutil.which("gitleaks") or next(
    (str(p) for p in Path(os.environ.get("LOCALAPPDATA", "/nonexistent"), "Microsoft/WinGet/Packages").glob("Gitleaks.Gitleaks_*/gitleaks.exe")), None)


def _git(repo: Path, *a: str, env: dict | None = None):
    return calistir(["git", "-C", str(repo), *a], env=env)


def repolar() -> list[Path]:
    kok = Path(C["kok"])
    out = []
    for g in kok.rglob(".git"):
        repo = g.parent
        if len(repo.relative_to(kok).parts) > C["derinlik"] or any(a in str(repo) for a in C["atla"]):
            continue
        out.append(repo)
    return sorted(out)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def calistir_hepsi(deneme: bool) -> dict:
    liste = repolar()
    remote = {r: _git(r, "remote", "get-url", "origin").stdout.strip() for r in liste}
    paylasilan = {u for u, n in Counter(u for u in remote.values() if u).items() if n > 1}
    sonuc = {"repolar": [], "ok": True}
    for repo in liste:
        ad = str(repo.relative_to(C["kok"]))
        durum = _git(repo, "status", "--porcelain").stdout.strip()
        if not durum:
            continue
        kayit = {"repo": ad, "degisiklik": len(durum.splitlines())}
        url = remote[repo]
        if not url:
            kayit["durum"] = "remote yok, atlandi"
        elif _git(repo, "rev-parse", "--verify", "HEAD").returncode != 0:
            kayit["durum"] = "commit yok, atlandi"
        else:
            branch = C["branch"] + (f"-{_slug(repo.name)}" if url in paylasilan else "")
            kayit["branch"] = branch
            kayit.update(_snapshot(repo, branch, deneme))
            sonuc["ok"] &= kayit["durum"] in ("pushlandi", "deneme", "gitleaks yok, atlandi")
        log("git", f"{ad}: {kayit['durum']}")
        sonuc["repolar"].append(kayit)
    return sonuc


def _snapshot(repo: Path, branch: str, deneme: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(repo, "read-tree", "HEAD", env=env)
        _git(repo, "add", "-A", env=env)
        agac = _git(repo, "write-tree", env=env).stdout.strip()
        if not agac:
            return {"durum": "snapshot alinamadi"}
        commit = _git(repo, "commit-tree", agac, "-p", "HEAD", "-m", "wip: otomatik gece yedegi", env=env).stdout.strip()
    if deneme:
        return {"durum": "deneme", "commit": commit[:8]}
    if not GITLEAKS:
        return {"durum": "gitleaks yok, atlandi"}
    tarama = calistir([GITLEAKS, "git", str(repo), "--log-opts", f"HEAD..{commit}", "--no-banner", "--redact", "--exit-code", "1"])
    if tarama.returncode != 0:
        return {"durum": "gitleaks bulgu, atlandi", "bulgu": (tarama.stdout + tarama.stderr).count("Finding:")}
    p = _git(repo, "push", "--force", "origin", f"{commit}:refs/heads/{branch}")
    return {"durum": "pushlandi" if p.returncode == 0 else "push hatasi", "hata": p.stderr.strip().splitlines()[-1:]}
