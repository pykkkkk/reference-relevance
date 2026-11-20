#!/usr/bin/env python3
"""NLI-based claim/support verification with atomic claim splitting (v0.1.0 algorithm layer)."""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json, write_json  # noqa: E402

DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


def atomic_claims(text):
    """Split a claim into independently verifiable atoms (rule-based v0.1.0)."""
    text = (text or "").strip()
    parts = re.split(r"(?<=[。；;.!?])\s*|\s+and\s+|\s+并且\s+|\s+而且\s+", text)
    atoms = [p.strip(" ,，。．;；") for p in parts if len(p.strip()) > 8]
    return atoms or [text]


def build_pairs(data, needs_path=None, supply_path=None):
    if "pairs" in data:
        pairs = data["pairs"]
    elif needs_path and supply_path:
        needs = read_json(needs_path).get("needs", [])
        supply = read_json(supply_path).get("supply", [])
        smap = {s["ref_index"]: s for s in supply}
        pairs = []
        for n in needs:
            for c in n.get("citations", []):
                idx = c.get("ref_index")
                s = smap.get(idx, {})
                pairs.append({
                    "claim_id": n.get("claim_id"),
                    "ref_index": idx,
                    "claim": n.get("text", ""),
                    "evidence": s.get("abstract", "") or s.get("title", ""),
                    "evidence_level": s.get("evidence_level", "title_only"),
                })
    else:
        raise SystemExit("需要输入含 pairs 的 JSON，或同时提供 --needs 与 --supply")
    out = []
    for p in pairs:
        atoms = atomic_claims(p.get("claim", ""))
        for i, atom in enumerate(atoms):
            q = dict(p)
            q["atom_id"] = f"{p.get('claim_id', 'c')}_{i + 1}"
            q["claim"] = atom
            out.append(q)
    return out


def load_classifier(model_name):
    try:
        from transformers import pipeline
    except Exception as exc:
        return None, f"transformers/torch 不可用: {exc}"
    try:
        clf = pipeline("text-classification", model=model_name, top_k=None, truncation=True)
        return clf, None
    except Exception as exc:
        return None, f"模型加载失败: {exc}"


def normalize_output(raw):
    """Support both transformers 4.x (list[list[dict]]) and 5.x (list[dict])."""
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        return raw[0]
    return raw if isinstance(raw, list) else []


def map_label(label):
    l = label.lower()
    if "entail" in l or "support" in l:
        return "SUPPORT"
    if "contrad" in l or "refut" in l:
        return "REFUTE"
    return "NEUTRAL"


def main():
    ap = argparse.ArgumentParser(description="NLI claim-evidence verification")
    ap.add_argument("input", nargs="?", help="JSON with pairs, or - for stdin-style file omitted")
    ap.add_argument("--needs", help="needs.json")
    ap.add_argument("--supply", help="supply.json")
    ap.add_argument("-o", "--output", default=".reference-relevant/nli.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-atomize", action="store_true")
    args = ap.parse_args()

    data = read_json(args.input) if args.input else {}
    pairs = build_pairs(data, args.needs, args.supply)
    if args.no_atomize:
        pairs = [p for p in pairs if p.get("atom_id", "").endswith("_1")]

    clf, err = load_classifier(args.model)
    results = []
    if clf is None:
        print(f"[nli] WARNING: {err}; 输出 UNKNOWN 并要求 agent 按量规推理", file=sys.stderr)
        for p in pairs:
            results.append({**p, "direction": "UNKNOWN", "score": 0.0, "status": "model_unavailable"})
    else:
        for p in pairs:
            try:
                raw = clf({"text": p.get("evidence", ""), "text_pair": p.get("claim", "")})
                out = normalize_output(raw)
                probs = {map_label(x["label"]): float(x["score"]) for x in out if isinstance(x, dict)}
                direction = max(probs, key=probs.get)
                results.append({**p, "direction": direction, "score": round(probs.get(direction, 0), 4),
                                "probs": {k: round(v, 4) for k, v in probs.items()}, "status": "ok",
                                "evidence_level": p.get("evidence_level", "title_only")})
            except Exception as exc:
                results.append({**p, "direction": "UNKNOWN", "score": 0.0, "status": f"error: {exc}"})
        print(f"[nli] {len(results)} atoms judged with {args.model}")

    out = {"model": args.model, "status": "unavailable" if clf is None else "ok",
           "note": "NLI 输出须遵守 evidence_level：abstract_only 不得判 D；REFUTE 一票否决",
           "results": results}
    write_json(args.output, out)
    print(f"[nli] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
