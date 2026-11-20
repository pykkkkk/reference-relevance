#!/usr/bin/env python3
"""Pre-flight source correctness check: existence and metadata accuracy for cited works."""
import argparse
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import (  # noqa: E402
    cache_get, cache_set, http_get_json, jaccard, last_name,
    normalize, read_json, write_json,
)

CACHE = ".reference-relevant/cache"


def is_zh(text):
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def crossref_lookup(ref, online=True):
    doi = (ref.get("doi") or "").strip()
    if doi:
        key = "doi:" + normalize(doi)
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    else:
        if not ref.get("title"):
            return None, "missing_title"
        key = "title:" + normalize(ref["title"])
        url = "https://api.crossref.org/works?query.bibliographic=" + urllib.parse.quote(ref["title"]) + "&rows=5"
    data = cache_get(CACHE, "crossref_verify", key, ttl_days=14)
    if data is None:
        if not online:
            return None, "offline_no_cache"
        data = http_get_json(url)
        cache_set(CACHE, "crossref_verify", key, data)
    msg = data.get("message") or {}
    items = [msg] if doi and msg.get("DOI") else (msg.get("items") or [])
    if not items:
        return None, "no_result"

    def authors(item):
        return "; ".join(
            " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
            for a in item.get("author", [])
        )

    scored = []
    for it in items:
        title = (it.get("title") or [""])[0]
        sim = jaccard(ref.get("title", ""), title)
        year_parts = ((it.get("published-print") or it.get("published-online") or {}).get("date-parts") or [[""]])[0]
        year = str(year_parts[0]) if year_parts else ""
        if ref.get("year") and year == str(ref["year"]):
            sim += 0.25
        if last_name(ref.get("authors", "")) and any(
            last_name(a.get("family", "")) == last_name(ref["authors"]) for a in it.get("author", [])
        ):
            sim += 0.25
        scored.append((sim, it, title, year, authors(it)))
    scored.sort(key=lambda x: x[0], reverse=True)
    sim, it, title, year, auth = scored[0]
    if sim < 0.55:
        return None, "low_similarity"
    biblio = it.get("biblio") or {}
    return {
        "source": "Crossref", "title": title, "authors": auth, "year": year,
        "venue": (it.get("container-title") or [""])[0],
        "doi": it.get("DOI", ""), "volume": biblio.get("volume", "") or it.get("volume", ""),
        "issue": biblio.get("issue", "") or it.get("issue", ""),
        "pages": biblio.get("page", "") or it.get("page", ""),
        "type": it.get("type", ""), "publisher": it.get("publisher", ""),
        "score": round(float(sim), 3),
    }, None


def openalex_lookup(ref, online=True):
    if not ref.get("title"):
        return None, "missing_title"
    key = "title:" + normalize(ref["title"])
    data = cache_get(CACHE, "openalex_verify", key, ttl_days=14)
    if data is None:
        if not online:
            return None, "offline_no_cache"
        url = "https://api.openalex.org/works?search=" + urllib.parse.quote(ref["title"]) + "&per_page=5"
        data = http_get_json(url)
        cache_set(CACHE, "openalex_verify", key, data)
    items = data.get("results") or []
    if not items:
        return None, "no_result"
    scored = []
    for it in items:
        title = it.get("display_name", "")
        sim = jaccard(ref.get("title", ""), title)
        if ref.get("year") and str(it.get("publication_year", "")) == str(ref["year"]):
            sim += 0.25
        scored.append((sim, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    sim, it = scored[0]
    if sim < 0.55:
        return None, "low_similarity"
    auths = [a.get("author", {}).get("display_name", "") for a in it.get("authorships", [])]
    biblio = it.get("biblio") or {}
    return {
        "source": "OpenAlex", "title": it.get("display_name", ""),
        "authors": "; ".join(auths), "year": str(it.get("publication_year", "")),
        "venue": ((it.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
        "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
        "volume": biblio.get("volume", ""), "issue": biblio.get("issue", ""),
        "pages": "–".join(filter(None, [biblio.get("first_page"), biblio.get("last_page")])),
        "type": it.get("type", ""), "publisher": "", "score": round(float(sim), 3),
    }, None


def compare_fields(ref, found):
    mismatches, warnings, missing = [], [], []
    if jaccard(ref.get("title", ""), found.get("title", "")) < 0.6:
        mismatches.append("title")
    if not found.get("authors") or not any(
        last_name(found.get("authors", "")) in last_name(a) or last_name(a) in last_name(found.get("authors", ""))
        for a in (ref.get("authors") or "").split(" and ")
    ):
        mismatches.append("authors")
    if ref.get("year") and found.get("year"):
        try:
            diff = abs(int(ref["year"]) - int(found["year"]))
            if diff > 2:
                mismatches.append("year")
            elif diff:
                warnings.append(f"year differs by {diff}")
        except ValueError:
            warnings.append("year not numeric")
    if ref.get("venue") and found.get("venue") and jaccard(ref["venue"], found["venue"]) < 0.35:
        mismatches.append("venue")
    if ref.get("doi") and found.get("doi") and normalize(ref["doi"]) != normalize(found["doi"]):
        mismatches.append("doi")
    for field in ("volume", "issue", "pages"):
        if ref.get(field) and found.get(field) and normalize(str(ref[field])) != normalize(str(found[field])):
            mismatches.append(field)
        elif not ref.get(field) and found.get(field):
            missing.append(field)
        elif ref.get(field) and not found.get(field):
            warnings.append(f"{field} not verifiable from source")
    return mismatches, warnings, missing


def suggest_bibtex(ref, found):
    key = ref.get("bib_key") or f"ref{ref.get('index', 0)}"
    typ = "book" if "book" in (found.get("type") or "") else "article"
    lines = [f"@{typ}{{{key},"]
    for field, val in [
        ("title", found.get("title")), ("author", found.get("authors")),
        ("journal" if typ == "article" else "publisher", found.get("venue") or found.get("publisher")),
        ("year", found.get("year")), ("volume", found.get("volume")),
        ("number", found.get("issue")), ("pages", found.get("pages")), ("doi", found.get("doi")),
    ]:
        if val:
            lines.append(f"  {field} = {{{str(val).strip()}}},")
    lines.append("}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Check existence and metadata accuracy of cited works")
    ap.add_argument("parsed", help="parsed.json from parse_document.py")
    ap.add_argument("-o", "--output", default=".reference-relevant/source_check.json")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    parsed = read_json(args.parsed)
    online = not args.offline
    items, degraded = [], False
    for ref in parsed.get("references", []):
        found, err = None, None
        for fn in (crossref_lookup, openalex_lookup):
            try:
                found, err = fn(ref, online)
            except Exception as exc:
                msg = str(exc)
                if "429" in msg or "rate" in msg.lower() or "budget" in msg.lower():
                    degraded = True
                err = msg
            if "429" in str(err or "") or "rate" in str(err or "").lower() or "budget" in str(err or "").lower():
                degraded = True
            if found:
                break
        if found:
            mismatches, warnings, missing = compare_fields(ref, found)
            status = "needs_fix" if mismatches or missing else "pass"
        elif is_zh(ref.get("title", "")):
            status, mismatches, warnings, missing = "unverifiable_zh", [], ["中文来源未接入，无法核验元数据"], []
        elif degraded or (err and "offline" in str(err).lower()):
            status, mismatches, warnings, missing = "unverifiable_degraded", [], ["证据源不可用，无法判断是否存在，不得断言编造"], []
        else:
            status, mismatches, warnings, missing = "fabricated_suspected", ["no trusted source matched"], [], []
        items.append({
            "ref_index": ref.get("index"), "bib_key": ref.get("bib_key"),
            "input": {k: ref.get(k) for k in ("title", "authors", "year", "venue", "doi", "volume", "number", "pages")},
            "found": found, "status": status,
            "mismatches": mismatches, "warnings": warnings, "missing_fields": missing,
            "suggested_bibtex": suggest_bibtex(ref, found) if found and status == "needs_fix" else "",
            "lookup_error": err,
        })
        if online:
            time.sleep(0.4)

    blocking = any(i["status"] in ("needs_fix", "fabricated_suspected") for i in items)
    out = {
        "mode": "degraded" if degraded else "normal",
        "note": "来源正确性不通过时不得进入相关性评估；unverifiable_* 不得断言编造，须人工确认；fabricated_suspected 不得自动改写",
        "blocking": blocking,
        "summary": {s: sum(1 for i in items if i["status"] == s)
                    for s in ("pass", "needs_fix", "fabricated_suspected", "unverifiable_zh", "unverifiable_degraded")},
        "items": items,
    }
    print(f"[source-check] {len(items)} refs; blocking={blocking}; summary={out['summary']}")
    if degraded:
        print("[source-check] WARNING: API 限额/网络降级；不得据此断言文献不存在", file=sys.stderr)
    write_json(args.output, out)
    print(f"[source-check] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
