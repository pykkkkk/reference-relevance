#!/usr/bin/env python3
"""Deterministic scoring from rubric v0.2: weights, veto, evidence caps, grade."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json, write_json  # noqa: E402

WEIGHTS = {
    "功能匹配": 0.25,
    "对象匹配": 0.15,
    "命题支持": 0.30,
    "方向性": 0.10,
    "证据强度": 0.10,
    "时效与版本": 0.05,
    "一手性与可核验性": 0.05,
}
CAPS = {"full_text": 1.0, "abstract_only": 0.6, "title_only": 0.45, "unverifiable": 0.3}


def score_one(item):
    scores = {k: float(item.get("scores", {}).get(k, 0)) for k in WEIGHTS}
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    direction = item.get("direction", "UNKNOWN")
    decorative = bool(item.get("decorative", False))
    evidence = item.get("evidence_level", "title_only")
    cap = CAPS.get(evidence, 0.3)

    veto = direction == "REFUTE"
    suspected = False
    abstain = bool(item.get("abstain", False))

    if veto:
        grade, action = "D", "replace_citation"
    elif evidence == "title_only":
        grade, action = "C", "rewrite_text"  # 仅题录：不判支撑性，强制人工
        abstain = True
        suspected = total < 0.40
    elif evidence in ("abstract_only", "unverifiable"):
        if total < 0.40:
            grade = "C"
            suspected = True
            abstain = True
            action = item.get("action", {}).get("type", "rewrite_text")
        elif total >= 0.85:
            grade, action = "B", "keep"  # 摘要级证据不给 A
        elif total >= 0.65:
            grade, action = "B", "keep"
        else:
            grade, action = "C", item.get("action", {}).get("type", "rewrite_text")
    else:
        if total >= 0.85 and not decorative:
            grade, action = "A", "keep"
        elif total >= 0.65:
            grade, action = "B", "keep"
        elif total >= 0.40 or decorative:
            grade, action = "C", item.get("action", {}).get("type", "rewrite_text")
        else:
            grade, action = "D", "replace_citation"

    confidence = min(float(item.get("confidence", 0.5)), cap)
    if confidence < 0.6:
        abstain = True
    out = dict(item)
    out.update({
        "computed_total": round(total, 4),
        "grade": grade,
        "confidence": round(confidence, 4),
        "confidence_cap": cap,
        "abstain": abstain,
        "suspected_mismatch": suspected,
        "veto": veto,
        "action": {"type": action, "detail": item.get("action", {}).get("detail", "")},
    })
    return out


def main():
    ap = argparse.ArgumentParser(description="Apply rubric v0.2 scoring deterministically")
    ap.add_argument("assessment", help="assessment.json from agent (with dimension scores)")
    ap.add_argument("-o", "--output", default=".reference-relevant/scored.json")
    args = ap.parse_args()
    data = read_json(args.assessment)
    items = data.get("assessments", data) if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = [items]
    scored = [score_one(x) for x in items]
    out = {k: v for k, v in data.items() if k != "assessments"} if isinstance(data, dict) else {}
    out["assessments"] = scored
    out["scoring_engine"] = "rubric-v0.2-deterministic"
    out["weights"] = WEIGHTS
    print(f"[score] {len(scored)} items; grades: " + str({g: sum(1 for x in scored if x['grade'] == g) for g in "ABCD"}))
    write_json(args.output, out)
    print(f"[score] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
