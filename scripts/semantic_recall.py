#!/usr/bin/env python3
"""Semantic recall via SPECTER2/sentence-transformers; lexical fallback when unavailable."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json, write_json  # noqa: E402
from search_candidates import bm25_scores  # noqa: E402

DEFAULT_MODEL = "sentence-transformers/allenai-specter"


def load_model(model_name):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        return None, f"sentence-transformers 不可用: {exc}"
    try:
        return SentenceTransformer(model_name), None
    except Exception as exc:
        return None, f"模型加载失败: {exc}"


def cos_sim(a, b):
    import numpy as np
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return []
    na, nb = np.linalg.norm(a, axis=1, keepdims=True), np.linalg.norm(b, axis=1, keepdims=True)
    na[na == 0] = 1e-9
    nb[nb == 0] = 1e-9
    return (a / na @ (b / nb).T).tolist()


def main():
    ap = argparse.ArgumentParser(description="Semantic re-ranking of candidates")
    ap.add_argument("candidates", help="candidates.json from search_candidates.py")
    ap.add_argument("-o", "--output", default=".reference-relevant/candidates_semantic.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    data = read_json(args.candidates)
    groups = data.get("candidates", [])
    model, err = load_model(args.model)
    if model is None:
        print(f"[semantic] WARNING: {err}; 回退 BM25（语义召回不可用，结果标 lexical_fallback）", file=sys.stderr)

    out_groups = []
    for g in groups:
        cands = g.get("candidates", [])
        if not cands:
            out_groups.append({**g, "candidates": [], "recall": "unavailable"})
            continue
        docs = [f"{c.get('title','')} {c.get('abstract','')}" for c in cands]
        query = " ".join([g.get("need", {}).get("function", ""), g.get("query", "")]).strip()
        if model is not None:
            try:
                qv = model.encode([query], normalize_embeddings=True)
                dv = model.encode(docs, normalize_embeddings=True)
                sims = cos_sim(qv, dv)[0]
                recall = "specter2"
            except Exception as exc:
                print(f"[semantic] encode failed: {exc}; fallback BM25", file=sys.stderr)
                sims = bm25_scores(query, docs)
                recall = "lexical_fallback"
        else:
            sims = bm25_scores(query, docs)
            recall = "lexical_fallback"
        ranked = sorted(zip(cands, sims), key=lambda x: x[1], reverse=True)[:args.top_k]
        out_groups.append({**g, "recall": recall,
                           "candidates": [{**c, "semantic_score": round(float(s), 4)} for c, s in ranked]})
    out = {**data, "candidates": out_groups, "model": args.model if model else None}
    write_json(args.output, out)
    print(f"[semantic] {len(out_groups)} groups, recall={out_groups[0]['recall'] if out_groups else 'n/a'}")
    print(f"[semantic] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
