"""Shared helpers for reference-relevant scripts."""
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAILTO = os.environ.get("RR_MAILTO", "")
USER_AGENT = "reference-relevant/0.1.0 (academic research assistant)" + (f" mailto:{MAILTO}" if MAILTO else "")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"\s+", " ", text).strip()


def jaccard(a, b):
    a, b = normalize(a), normalize(b)
    wa = {w for w in re.findall(r"[a-z]{3,}|[\u4e00-\u9fff]{2,}", a)}
    wb = {w for w in re.findall(r"[a-z]{3,}|[\u4e00-\u9fff]{2,}", b)}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def last_name(authors):
    if not authors:
        return ""
    first = str(authors).split(",")[0].strip()
    first = re.sub(r"\s+(et al\.?|and others?|and colleagues?)\s*$", "", first, flags=re.I)
    parts = first.split()
    return parts[-1].lower() if parts else ""


def strip_latex(text):
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", "", text or "")
    return re.sub(r"\s+", " ", text.replace("\\", "")).strip()


def split_sentences(text):
    """Split on Chinese and English sentence terminators, keeping punctuation."""
    text = (text or "").replace("\n", " ")
    parts = re.split(r"(?<=[。！？；.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def cache_key(source, query):
    return hashlib.sha256(f"{source}|{normalize(query)}".encode("utf-8")).hexdigest()[:16]


def cache_get(cache_dir, source, query, ttl_days=7):
    p = Path(cache_dir) / f"{source}_{cache_key(source, query)}.json"
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > ttl_days * 86400:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(cache_dir, source, query, value):
    p = Path(cache_dir) / f"{source}_{cache_key(source, query)}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return p


def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_text(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def reconstruct_abstract(inv):
    if not inv:
        return ""
    positions = []
    for word, poss in inv.items():
        for pos in poss:
            positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)
