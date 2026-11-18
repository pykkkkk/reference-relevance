#!/usr/bin/env python3
"""Retrieve and pre-rank replacement candidates with BM25."""
import argparse
import math
import re
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import (  # noqa: E402
    cache_get, cache_set, http_get_json, read_json, reconstruct_abstract, write_json,
)

FUNCTION_TERMS = {
    "理论/假说依据": "theory hypothesis framework",
    "数据/测量来源": "data source measurement scale",
    "计量识别策略": "difference in differences instrumental variable identification",
    "变量定义/指标构建": "variable measurement index construction",
    "模型假设来源": "model assumption",
    "定理/命题来源": "theorem proposition proof",
    "求解方法": "solution method algorithm",
}

TOKEN = re.compile(r"[a-z]{2,}|[\u4e00-\u9fff]{2}")


def tokenize(text):
    text = (text or "").lower()
    out = []
    for m in TOKEN.finditer(text):
        w = m.group(0)
        if re.match(r"[\u4e00-\u9fff]", w):
            out.extend(w[i:i + 2] for i in range(len(w) - 1))
        else:
            out.append(w)
    return out


def bm25_scores(query, docs, k1=1.5, b=0.75):
    q = tokenize(query)
    if not q or not docs:
        return [0.0] * len(docs)
    avg = sum(len(d) for d in docs) / len(docs) or 1.0
    df = Counter()
    for d in docs:
        df.update(set(tokenize(d)))
    n = len(docs)
    idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
    scores = []
    for d in docs:
        toks = tokenize(d)
        tf = Counter(toks)
        dl = len(toks)
        s = 0.0
        for w in set(q):
            if w not in tf:
                continue
            s += idf.get(w, 0) * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * dl / avg))
        scores.append(s)
    return scores


def openalex_search(query, rows=20):
    key = "candidates:" + query.strip().lower()
    data = cache_get(".reference-relevant/cache", "candidates", key, ttl_days=1)
    if data is None:
        url = "https://api.openalex.org/works?search=" + urllib.parse.quote(query) + f"&per_page={rows}"
        data = http_get_json(url)
        cache_set(".reference-relevant/cache", "candidates", key, data)
    return data.get("results", [])


def main():
    ap = argparse.ArgumentParser(description="Retrieve and pre-rank replacement candidates")
    ap.add_argument("--assessment", default=".reference-relevant/assessment.json")
    ap.add_argument("-o", "--output", default=".reference-relevant/candidates.json")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    data = read_json(args.assessment)
    entries = data.get("assessments", data) if isinstance(data, dict) else data
    if isinstance(entries, dict):
        entries = [entries]
    targets = [e for e in entries if e.get("grade") in ("C", "D") or (e.get("action") or {}).get("type") in ("replace_citation", "add_citation")]
    out = []
    for e in targets:
        need = e.get("need", {})
        function = need.get("function", "")
        query = " ".join([e.get("text", ""), FUNCTION_TERMS.get(function, function)]).strip()
        items = []
        if not args.offline:
            try:
                items = openalex_search(query, rows=max(20, args.top_k * 4))
            except Exception as exc:
                print(f"[search] retrieval failed for {e.get('claim_id')}: {exc}", file=sys.stderr)
            time.sleep(0.4)
        docs = [f"{it.get('display_name', '')} {reconstruct_abstract(it.get('abstract_inverted_index'))}" for it in items]
        scores = bm25_scores(query, docs)
        ranked = sorted(zip(items, scores), key=lambda x: x[1], reverse=True)[:args.top_k]
        out.append({
            "claim_id": e.get("claim_id"),
            "need": need,
            "query": query,
            "candidates": [{
                "title": it.get("display_name", ""),
                "year": it.get("publication_year"),
                "venue": ((it.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
                "abstract": reconstruct_abstract(it.get("abstract_inverted_index")),
                "bm25": round(float(s), 4),
                "source": "OpenAlex",
                "verification": "pending",
            } for it, s in ranked],
        })
    print(f"[search] {len(out)} targets, top_k={args.top_k}")
    write_json(args.output, {"candidates": out, "note": "候选须按 rubric.md 用同一标准重排并经 fetch_metadata.py 验真"})
    print(f"[search] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
