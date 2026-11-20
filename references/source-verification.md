# 来源正确性前置检查

在相关性评估之前执行。目的不是做全面文献计量，而是确保用于评估的文献条目**真实存在且著录字段正确**；否则后续的相关性判断建立在错误对象上。

## 检查项

| 项目 | 判定 |
|---|---|
| 是否存在 | DOI / 题名在 Crossref、OpenAlex 等可信库中查找；多源无命中才标 `fabricated_suspected` |
| 作者 | 至少一位作者姓氏与库中记录一致 |
| 题名 | 规范化后 Jaccard 相似度 ≥ 0.6 |
| 年份 | 与库中记录差异 ≤ 2 年；更大差异判 `needs_fix` |
| 期刊 / 来源 | 与库中记录相似度 ≥ 0.35 |
| DOI | 若正文已有 DOI，必须与库中 DOI 一致 |
| 卷 / 期 / 页码 | 若两边都有则必须一致；若原条目缺失而库中可得，记入 `missing_fields` 并建议补齐 |

## 输出状态

- `pass`：来源正确，进入相关性评估。
- `needs_fix`：来源存在但字段错误或缺失；先按 `suggested_bibtex` 修正，再进入评估。
- `fabricated_suspected`：多源均无命中，**不得自动改写**，须人工确认是否编造或来源特殊。
- `unverifiable_zh`：中文来源未接入，无法核验；按 `cn-sources.md` 输出「无法核验」，不得判为编造。
- `unverifiable_degraded`：API 限额/离线导致无法核验；不得判为编造，须用户确认是否继续。

## 处理顺序

1. 运行 `python scripts/verify_sources.py .reference-relevant/parsed.json -o .reference-relevant/source_check.json`；
2. 若 `blocking=true`，停止后续相关性评估；
3. 对 `needs_fix` 条目运行 `python scripts/apply_source_fixes.py ... -o .reference-relevant/source_fixes.diff`，检查 diff，确认后加 `--apply` 写回；
4. 重新解析并重新核验，直到不存在阻断项；
5. 对 `unverifiable_zh` / `unverifiable_degraded` 条目，必须向用户说明限制并取得确认后，才能继续。

## 与相关性评估的关系

来源正确性是前置条件，不是评分维度。字段修正后仍按原有需求—供给框架评估相关性；同一套评分标准继续用于替换候选筛选。
