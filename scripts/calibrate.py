#!/usr/bin/env python3
"""Confidence calibration: ECE, Brier, Platt scaling and isotonic regression (numpy-only)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json, write_json  # noqa: E402

import numpy as np  # noqa: E402


def ece(y, p, bins=10):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum():
            total += m.sum() / len(p) * abs(y[m].mean() - p[m].mean())
    return float(total)


def brier(y, p):
    return float(np.mean((np.asarray(y, dtype=float) - np.asarray(p, dtype=float)) ** 2))


def platt_fit(y, p, epochs=2000, lr=0.05):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    a, b = 1.0, 0.0
    for _ in range(epochs):
        z = a * np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))) + b
        pred = 1 / (1 + np.exp(-z))
        err = pred - y
        a -= lr * np.mean(err * np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))))
        b -= lr * np.mean(err)
    return float(a), float(b)


def platt_apply(p, a, b):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return (1 / (1 + np.exp(-(a * np.log(p / (1 - p)) + b)))).tolist()


def isotonic_fit(y, p):
    """PAVA: returns breakpoints (thresholds, values)."""
    order = np.argsort(p)
    ps, ys = np.asarray(p)[order], np.asarray(y)[order]
    blocks = [[float(v), [float(w)]] for v, w in zip(ps, ys)]
    i = 0
    while i < len(blocks) - 1:
        if np.mean(blocks[i][1]) > np.mean(blocks[i + 1][1]) + 1e-12:
            blocks[i][1].extend(blocks[i + 1][1])
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    return [(float(np.mean([t[0] for t in [b]])), float(np.mean(b[1]))) for b in blocks]


def isotonic_apply(p, breaks):
    out = []
    for x in p:
        val = breaks[0][1] if breaks else 0.5
        for th, v in breaks:
            if x >= th:
                val = v
        out.append(float(val))
    return out


def load_pairs(path):
    data = read_json(path)
    rows = data.get("calibration", data) if isinstance(data, dict) else data
    out = []
    for r in rows:
        pred = r.get("confidence", r.get("score", r.get("predicted")))
        gold = r.get("gold")
        if pred is None or gold is None:
            continue
        if isinstance(gold, str):
            gold = 1.0 if gold in ("A", "B", "keep", "correct") else 0.0
        out.append((float(pred), float(gold)))
    if not out:
        raise SystemExit("未找到可校准样本：需要 confidence/score 与 gold 字段")
    return out


def main():
    ap = argparse.ArgumentParser(description="Calibrate confidence scores")
    ap.add_argument("labels", help="JSON list with confidence/score and gold")
    ap.add_argument("-o", "--output", default=".reference-relevant/calibration.json")
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()

    pairs = load_pairs(args.labels)
    p = np.array([x[0] for x in pairs])
    y = np.array([x[1] for x in pairs])
    base = {"n": len(pairs), "base_ece": ece(y, p, args.bins), "base_brier": brier(y, p)}
    a, b = platt_fit(y, p)
    pp = platt_apply(p, a, b)
    breaks = isotonic_fit(y, p)
    pi = isotonic_apply(p, breaks)
    out = {
        **base,
        "method": "platt+isotonic",
        "platt": {"a": a, "b": b, "ece": ece(y, pp, args.bins), "brier": brier(y, pp)},
        "isotonic": {"breaks": breaks, "ece": ece(y, pi, args.bins), "brier": brier(y, pi)},
        "note": "用校准参数替换 assessment.json 的 confidence；低置信度仍须 abstain",
    }
    print(f"[calibrate] n={len(pairs)} base ECE={base['base_ece']:.4f} Brier={base['base_brier']:.4f}")
    print(f"[calibrate] platt  ECE={out['platt']['ece']:.4f} Brier={out['platt']['brier']:.4f}")
    print(f"[calibrate] iso    ECE={out['isotonic']['ece']:.4f} Brier={out['isotonic']['brier']:.4f}")
    write_json(args.output, out)
    print(f"[calibrate] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
