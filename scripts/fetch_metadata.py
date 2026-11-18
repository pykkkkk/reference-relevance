#!/usr/bin/env python3
"""Fetch real abstracts and verify references from trusted sources."""
import argparse
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import (  # noqa: E402
    cache_get, cache_set, http_get_json, jaccard, last_name, normalize,
    read_json, reconstruct_abstract, write_json,
)


def _crossref(ref, online=True):
    doi = (ref.get("doi") or "").strip()
    if doi:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
        key = "doi:" + normalize(doi)
    else:
        if not ref.get("title"):
            return None
        key = "title:" + normalize(ref["title"])
        url = "https://api.crossref.org/works?query.title=" + urllib.parse.quote(ref["title"]) + "&rows=3"
    data = cache_get(".reference-relevant/cache", "crossref", key)
    if data is None:
        if not online:
            return None
        data = http_get_json(url)
        cache_set(".reference-relevant/cache", "crossref", key, data)
    items = (data.get("message") or {}).get("items") or []
    if doi and data.get("message", {}).get("DOI"):
        items = [data["message"]]
    best = None
    best_score = -1.0
    for it in items:
        title = (it.get("title") or [""])[0]
        score = jaccard(ref.get("title", ""), title)
        if ref.get("year") and str(it.get("published-print", {}).get("date-parts", [[""]])[0][0]) == str(ref["year"]):
            score += 0.3
        if last_name(ref.get("authors", "")) and any(last_name(a.get("family", "")) == last_name(ref["authors"]) for a in it.get("author", [])):
            score += 0.2
        if score > best_score:
            best_score, best = score, it
    if best is None or best_score < 0.4:
        return None
    pub = best.get("published-print") or best.get("published-online") or {}
    parts = (pub.get("date-parts") or [[""]])[0]
    return {
        "title": (best.get("title") or [""])[0],
        "year": str(parts[0]) if parts else "",
        "venue": (best.get("container-title") or [""])[0],
        "doi": best.get("DOI", ""),
        "abstract": re.sub(r"<[^>]+>", "", best.get("abstract", "")),
        "score": best_score,
        "source": "Crossref",
    }


def _s2(ref, online=True):
    if not ref.get("title"):
        return None
    key = "title:" + normalize(ref["title"])
    data = cache_get(".reference-relevant/cache", "s2", key)
    if data is None:
        if not online:
            return None
        fields = "title,authors,year,abstract,venue,externalIds"
        url = "https://api.semanticscholar.org/graph/v1/paper/search?query=" + urllib.parse.quote(ref["title"]) + f"&fields={fields}&limit=3"
        data = http_get_json(url)
        cache_set(".reference-relevant/cache", "s2", key, data)
    items = data.get("data") or []
    best, best_score = None, -1.0
    for it in items:
        score = jaccard(ref.get("title", ""), it.get("title", ""))
        if ref.get("year") and str(it.get("year", "")) == str(ref["year"]):
            score += 0.3
        if last_name(ref.get("authors", "")) and any(last_name(a.get("name", "")) == last_name(ref["authors"]) for a in it.get("authors", [])):
            score += 0.2
        if score > best_score:
            best_score, best = score, it
    if best is None or best_score < 0.4:
        return None
    return {
        "title": best.get("title", ""),
        "year": str(best.get("year", "")),
        "venue": best.get("venue", "") or "",
        "doi": (best.get("externalIds") or {}).get("DOI", ""),
        "abstract": best.get("abstract", "") or "",
        "score": best_score,
        "source": "SemanticScholar",
    }


def _openalex(ref, online=True):
    if not ref.get("title"):
        return None
    key = "title:" + normalize(ref["title"])
    data = cache_get(".reference-relevant/cache", "openalex", key)
    if data is None:
        if not online:
            return None
        url = "https://api.openalex.org/works?search=" + urllib.parse.quote(ref["title"]) + "&per_page=3"
        data = http_get_json(url)
        cache_set(".reference-relevant/cache", "openalex", key, data)
    items = data.get("results") or []
    best, best_score = None, -1.0
    for it in items:
        score = jaccard(ref.get("title", ""), it.get("display_name", ""))
        if ref.get("year") and str(it.get("publication_year", "")) == str(ref["year"]):
            score += 0.3
        if score > best_score:
            best_score, best = score, it
    if best is None or best_score < 0.4:
        return None
    return {
        "title": best.get("display_name", ""),
        "year": str(best.get("publication_year", "")),
        "venue": ((best.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
        "doi": (best.get("doi") or "").replace("https://doi.org/", ""),
        "abstract": reconstruct_abstract(best.get("abstract_inverted_index")),
        "score": best_score,
        "source": "OpenAlex",
    }


def main():
    ap = argparse.ArgumentParser(description="Fetch metadata and verify references")
    ap.add_argument("parsed", help="parsed.json from parse_document.py")
    ap.add_argument("-o", "--output", default=".reference-relevant/supply.json")
    ap.add_argument("--offline", action="store_true", help="only use cached responses")
    ap.add_argument("--abstract-only", action="store_true", help="force title+abstract degradation mode; never claim full-text evidence")
    args = ap.parse_args()

    parsed = read_json(args.parsed)
    online = not args.offline
    results = []
    degraded = args.abstract_only
    for ref in parsed.get("references", []):
        hits = []
        for fn in (_crossref, _s2, _openalex):
            try:
                hit = fn(ref, online)
                if hit:
                    hits.append(hit)
            except Exception as exc:
                msg = str(exc)
                if "429" in msg or "too many requests" in msg.lower() or "rate" in msg.lower() or "budget" in msg.lower():
                    degraded = True
                hits.append({"source": fn.__name__, "error": msg, "score": 0})
            if online:
                time.sleep(0.4)
        good = [h for h in hits if h.get("score", 0) >= 0.5 and not h.get("error")]
        warnings = []
        chosen = sorted(good, key=lambda h: (h["score"], h["source"] == "Crossref"), reverse=True)
        best = chosen[0] if chosen else None
        if best and ref.get("year") and best.get("year") and str(ref["year"]) != str(best["year"]):
            warnings.append(f"year mismatch: ref={ref['year']}, found={best['year']}")
        if not best:
            warnings.append("no trusted source matched; treat as unverifiable, not nonexistent")
        verification = "verified" if len(good) >= 2 else ("weak_verified" if good else "unverifiable")
        abstract = best.get("abstract", "") if best else ""
        evidence_level = "abstract_only" if abstract else "title_only"
        if evidence_level == "abstract_only":
            warnings.append("仅题目+摘要证据：置信度上限 0.6，不得据此判 D")
        else:
            warnings.append("仅题录证据：置信度上限 0.45，强制转人工，不得判 D")
        if degraded:
            warnings.append("API 额度不足/强制降级：未获取全文证据")
        results.append({
            "ref_index": ref["index"],
            "title": best.get("title") if best else ref.get("title", ""),
            "year": best.get("year") if best else ref.get("year"),
            "venue": best.get("venue") if best else ref.get("venue", ""),
            "doi": best.get("doi") if best else ref.get("doi", ""),
            "abstract": abstract,
            "abstract_source": best.get("source", "") if best else "",
            "verification": verification,
            "evidence_level": evidence_level,
            "degraded": bool(degraded),
            "warnings": warnings,
            "supply_profile": {
                "evidence_type": "UNKNOWN",
                "sample": "UNKNOWN",
                "direction_hint": "UNKNOWN",
                "source_layer": "UNKNOWN",
                "timeliness": "UNKNOWN",
            },
            "matched_sources": [h.get("source") for h in good],
        })
    print(f"[fetch] {len(results)} references processed" + (" [DEGRADED: title/abstract only]" if degraded else ""))
    write_json(args.output, {
        "discipline": parsed.get("discipline"),
        "mode": "degraded_abstract_only" if degraded else "normal",
        "evidence_policy": "仅题目+摘要时置信度上限 0.6；不得直接判 D；D 级需全文或人工确认",
        "supply": results,
    })
    print(f"[fetch] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
