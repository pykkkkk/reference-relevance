# 算法层

本目录的可确定性算法由脚本执行；需要语义理解的部分由 agent 按量规推理。

## 1. `score_relevance.py` — 确定性评分器

把 `rubric.md` 的判定规则代码化，不依赖外部模型：

- 七维加权：功能匹配 0.25 / 对象匹配 0.15 / 命题支持 0.30 / 方向性 0.10 / 证据强度 0.10 / 时效与版本 0.05 / 一手性与可核验性 0.05；
- REFUTE 一票否决 → D；
- 证据等级封顶：full_text 1.0 / abstract_only 0.6 / title_only 0.45 / unverifiable 0.3；
- 降级模式下低分不判 D，改为 C + `suspected_mismatch: true` + `abstain: true`；
- `title_only` 一律强制弃权、不判支撑性。

```bash
python scripts/score_relevance.py .reference-relevant/assessment.json -o .reference-relevant/scored.json
```

## 2. `nli_verify.py` — 主张—证据三态判定

- 默认模型 `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`，输出 SUPPORT / REFUTE / NEUTRAL 及概率；
- 内置规则化原子 claim 拆分（按句号和 `and / 并且 / 而且`），可用 `--no-atomize` 关闭；
- 输入可以是 `pairs`，或 `--needs needs.json --supply supply.json` 自动生成；
- `transformers/torch` 缺失时输出 `model_unavailable` + UNKNOWN，并提示 agent 按量规推理。

```bash
python scripts/nli_verify.py --needs .reference-relevant/needs.json \
  --supply .reference-relevant/supply.json -o .reference-relevant/nli.json
```

## 3. `semantic_recall.py` — 语义召回

- 默认 SPECTER2（`sentence-transformers/allenai-specter`）对 query 与候选做双塔余弦重排；
- 依赖缺失或编码失败时回退 BM25，标 `lexical_fallback`，不把回退结果当作语义判定；
- 与 `search_candidates.py` 的 `bm25_scores` 共用同一套 tokenize 逻辑。

```bash
python scripts/semantic_recall.py .reference-relevant/candidates.json \
  -o .reference-relevant/candidates_semantic.json --top-k 5
```

## 4. `calibrate.py` — 置信度校准

纯 numpy 实现，无需 sklearn：

- ECE（等宽分箱）与 Brier Score；
- Platt Scaling（logit 上 1D logistic）；
- Isotonic Regression（PAVA，保序）；
- 输入样本需含 `confidence` / `score` 与 `gold`（A/B/keep/correct 视为正例）。

```bash
python scripts/calibrate.py .reference-relevant/labels.json -o .reference-relevant/calibration.json
```

## 可选依赖

```bash
pip install transformers torch sentence-transformers
```

未安装时，评分器与校准器仍可运行，NLI 与语义召回按上述降级处理。

## 脚本 / agent 边界

- 脚本负责：加权、一票否决、证据封顶、弃权、原子拆分、向量相似度、校准曲线；
- agent 负责：功能分类、供给画像字段、证据句选择、候选理由解释；
- NLI 与语义召回若处于降级态，agent 必须显式在报告中标注，不得把退化结果当成模型判定。
