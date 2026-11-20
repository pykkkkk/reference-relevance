---
name: reference-relevant
version: 0.2.0
agent_created: true
description: 评估学术论文中已有引用是否与正文的引用需求匹配，发现无关/错配引用并检索更合适的替换文献。执行前先做文献来源正确性检查，发现疑似编造或元数据错误时先修正。当用户要求检查引用相关性、排查无关引用、判断文献是否支撑正文论断、为论断寻找或替换参考文献、审计引文归因、核验参考文献真实性时使用。适用学科为经管实证与建模论文，支持 Word .docx / PDF / LaTeX，中文 GB/T 7714 与 APA 作者—年份制。本 skill 不以格式规范检查为主，也不做全面漏引检测。
---

# Reference Relevant — 引用相关性决策助手

## Overview

按「需求先行、供给匹配」评估现有引用：先确保引用条目本身真实且著录正确，再读懂引用处正文想表达什么，推导该处的引用需求；然后判断已引文献是否满足该需求。只有判定不满足时，才用同一把尺子检索并排序替换候选。

**前置闸门**：文献来源正确性检查不通过时，先修正条目，不做相关性评估。这是为了防止在错误文献对象上计算「匹配度」。

本 skill 输出**证据与建议**，不代替作者做最终决定；替换默认只生成 diff，须显式确认才写回。

## 适用边界（先读）

- **主攻**：已有引用。无引用区域默认跳过；仅对重要概念、核心论断做「建议补引」提醒，不做全面漏引检查。
- **适用学科**：经管实证与建模论文。保留 `discipline` 参数，取值 `econ-empirical` / `econ-modeling`；两者使用不同需求模板。
- **前置**：每条引用都必须先通过来源正确性检查；存在性或作者 / 题名 / 期刊 / 年份 / 页码等字段有误时，先修正。详见 `references/source-verification.md`。
- **不做**：全面格式规范检查；绕过验证码或反爬获取中文文献。
- **中文能力边界**：CNKI 无公开 API；CNKI AI LINK 未覆盖经管；OpenAlex / Crossref 对中文经管核心期刊覆盖极差。查不到时输出「无法核验」，**不得**输出「文献不存在」。详见 `references/cn-sources.md`。
- **v0.1.0 限制**：语义召回、NLI 支撑性判定、置信度校准均由 agent 按量规推理完成，尚未接入专用模型；分数为决策辅助，不作绝对结论。

## Workflow

所有中间产物写入运行目录 `./.reference-relevant/`，不污染原稿目录。

### Step 0 — 解析文档

**引用标记的识别与功能分类由大模型（agent）直接完成**，不依赖正则规则；脚本只负责把文档转成带位置的文本块和参考文献条目。

```bash
python scripts/parse_document.py <input> -o .reference-relevant/raw.json [--discipline econ-empirical|econ-modeling]
```

`raw.json` 只提供 `references`、`blocks`、`parse_warnings` 等原始材料。随后 agent 阅读 `raw.json` 中的正文，按 `references/llm-parsing.md` 的规则直接写出 `.reference-relevant/parsed.json`：

- 识别每一处引用标记：作者—年份制（含 `et al.`、`&`、`and`、`e.g.`、`a la`、多次出现的同一文献）与编号制 `[1,2]`；
- 同一括号内多篇引用逐条拆分，每一条生成独立 `claim`，`ref_indices` 只填对应的那一篇；
- 同一定文献在全文出现多次时，按出现位置分别生成 `claim`，各自绑定所在句子；
- 在 `claim` 中直接写入 `function`（引用功能）与 `strength`（直接证据 / 间接背景），即 Step 1 的需求画像与解析合并完成；
- 输出字段必须包含 `claim_id`、`block_index`、`marker`、`author_hint`、`year_hint`、`text`、`context_before`、`context_after`、`ref_indices`、`function`、`strength`、`necessity`、`confidence`、`needs_review`。

**规则脚本的角色**：无大模型可用时，`parse_document.py` 可加 `--rule-claims` 直接产出 `parsed.json` 作为兜底；该路径受正则覆盖限制，报告中必须标注 `parsing_method: rule_based`，提示可能漏掉复杂引用格式。默认使用大模型解析路径，标 `parsing_method: llm`。

检查材料中的 `parse_warnings`：出现「参考文献切分失败」时先人工核对原稿，不继续评分。

### Step 0A — 来源正确性前置检查（硬性闸门）

```bash
python scripts/verify_sources.py .reference-relevant/parsed.json -o .reference-relevant/source_check.json
```

检查文献是否存在，以及作者、题名、期刊/来源、年份、DOI、卷期页码是否与可信库记录一致。输出 `source_check.json`，其中 `blocking=true` 表示存在必须先处理的问题。

处理规则：
- `needs_fix`：来源存在但字段有误或缺失。执行：
  ```bash
  python scripts/apply_source_fixes.py .reference-relevant/source_check.json --input <input> -o .reference-relevant/source_fixes.diff
  ```
  检查 diff，用户确认后才加 `--apply` 写回；重新解析并重新核验。
- `fabricated_suspected`：多源无命中，疑似编造。**不得自动改写**，须人工确认来源或删除该条引用。
- `unverifiable_zh` / `unverifiable_degraded`：无法核验，不等于不存在；向用户说明限制并取得确认后才能继续。
- 只要仍有 `blocking=true`，不得进入 Step 1 及后续评分。

### Step 1 — 需求画像（已并入 Step 0）

大模型解析时已在每个 `claim` 中写入 `function` / `strength` / `necessity`，无需重复判断。若使用规则兜底路径，则读取 `.reference-relevant/parsed.json`，对每个含引用的论断单元按 `references/citation_functions.md` 补齐这些字段，写入 `.reference-relevant/needs.json`。

要求：
- 以**可独立验证的论断**为单位，不以整句为单位；一句含多个论断时拆开。
- 记录章节、引用标记位置、相邻句等结构特征。
- 实证模板关注「理论/假说依据」「数据/测量来源」「计量识别策略」；建模模板关注「模型假设/定理来源」「求解方法」。
- 每位引用单独分配需求；`[1,2,3]` 不得共用一个判断。
- 低置信度需求标记 `needs_review: true`，不要强行归类。

### Step 2 — 供给画像（脚本取数）

```bash
python scripts/fetch_metadata.py .reference-relevant/parsed.json -o .reference-relevant/supply.json [--offline] [--abstract-only]
```

按 DOI/ID 优先、多源交叉校验获取真实摘要与元数据；中文来源单独路由。输出每篇文献的供给画像、`verification` 与 `evidence_level` 状态。

不得把 BibTeX 原始条目当作摘要使用。**API 返回 429 / 预算耗尽时脚本自动进入降级模式**：仅用题目 + 可得摘要，标 `evidence_level: abstract_only`（无摘要则 `title_only`）、`degraded: true`。也可显式加 `--abstract-only` 强制降级。

### Step 3 — 对齐评估（agent 推理）

读取 `.reference-relevant/needs.json` 与 `.reference-relevant/supply.json`。**先让脚本把 rubric 确定性部分算完**，再由 agent 补充语义判断：

```bash
python scripts/score_relevance.py .reference-relevant/assessment.json -o .reference-relevant/scored.json
```

`score_relevance.py` 负责加权、REFUTE 一票否决、证据等级封顶、降级不得判 D、`title_only` 强制弃权。详见 `references/algorithms.md`。

硬性规则：
- 三组维度：需求对齐 / 支撑性 / 供给质量。
- NLI 三态判定：REFUTE（反驳）**一票否决**，不得作为支持性供给；中性提不得当作直接证据。
- 论断必须原子化后逐条核验，每条附证据句（正文论断 + 文献原文/摘要片段）。
- 建模模板**跳过 NLI 支撑性判定**，改判「模型/假设/方法来源是否匹配」并转人工确认。
- 四级判定：A 直接支持 / B 背景可用 / C 弱相关需人工 / D 错配。
- 低置信度一律标记 `abstain: true`，转人工，不自动判为错配。
- **证据等级决定结论上限**：`abstract_only` 置信度 ≤ 0.6、不得判 D；`title_only` 置信度 ≤ 0.45、强制弃权。D 级必须来自全文证据句或作者人工确认。降级模式下疑似错配输出 C + `suspected_mismatch: true`，并建议人工读全文。

### Step 4 — 候选检索与重排（仅 C/D 级触发）

```bash
python scripts/search_candidates.py --assessment .reference-relevant/assessment.json -o .reference-relevant/candidates.json --top-k 5
```

脚本先做 BM25 词法召回；语义召回为可选算法层，默认关闭。候选必须来自可信学术库并逐条验真。**降级模式下候选只能按题目+摘要初排，禁止据此自动写回。**

如需语义重排：`python scripts/semantic_recall.py .reference-relevant/candidates.json -o .reference-relevant/candidates_semantic.json`；依赖缺失时自动回退 BM25 并标 `lexical_fallback`。

NLI 判定：`python scripts/nli_verify.py --needs .reference-relevant/needs.json --supply .reference-relevant/supply.json -o .reference-relevant/nli.json`；模型不可用时输出 UNKNOWN，由 agent 按量规推理。

校准：有人工标注后运行 `python scripts/calibrate.py labels.json -o .reference-relevant/calibration.json`。

agent 读取候选，按 `references/rubric.md` 的**同一套标准**重排，写入 `.reference-relevant/actions.json`。每个动作取值：`keep` / `rewrite_text` / `add_citation` / `remove_citation` / `replace_citation`，并附理由与证据。优先建议 `rewrite_text`：问题常在正文表述而非文献。

### Step 5 — 生成替换 diff（默认不写回）

```bash
python scripts/apply_replacement.py --actions .reference-relevant/actions.json --input <input> -o .reference-relevant/replacement.diff
```

仅生成 diff 与备份路径。**不得**加 `--apply`，除非用户明确确认；确认后脚本先备份原文件再写回，并保留审计记录。

### Step 6 — 输出报告

按 `assets/report-template.md` 生成 Markdown 报告：摘要统计、高置信问题清单、逐条明细（需求 / 现有供给 / 评分 / 证据 / 建议动作）、候选替换 diff、待用户确认事项。语气统一为「建议」，不输出「必须」。

## 降级模式（API 额度不足时的默认行为）

- 触发：Crossref / S2 / OpenAlex 返回 429、预算耗尽、网络不可用，或显式 `--abstract-only`。
- 手段：只用**题目 + 可得摘要**做主题/功能/对象匹配的初判，不声称全文级证据。
- 护栏：置信度上限 0.6；不判 D，只判 C + `suspected_mismatch: true`；不自动写回；报告中必须显示 `evidence_level` 与 `degraded` 状态。
- 恢复：配置机构 API key 后重跑 `fetch_metadata.py`，拿到摘要/全文再升级为正式判定。

## 脚本 / agent 边界

职责写死，避免流程歧义：

| 负责方 | 任务 |
|---|---|
| 脚本 | 解析文档、取元数据、验真、检索召回、生成 diff、备份与写回 |
| agent | 需求识别、供给评估、对齐打分、候选重排、置信度与理由 |

agent 不重复执行脚本可完成的取数工作；脚本不做语义判断。无需外部 LLM API key。

## Resources

### references/
- `rubric.md` — 相关性评分量规 v0.2（三组维度、四级判定、一票否决、证据句、置信度）
- `source-verification.md` — 来源正确性前置检查的字段、状态与处理顺序
- `algorithms.md` — 四个算法脚本（评分、NLI、语义召回、校准）的接口、依赖与降级状态
- `citation_functions.md` — 经管引用功能轴；实证与建模两个需求模板
- `llm-parsing.md` — 大模型引用解析的输入、输出字段与必须遵守的拆分规则
- `api-notes.md` — 英文数据源、限额、缓存、验真策略
- `cn-sources.md` — 中文来源能力边界与降级话术

### assets/
- `report-template.md` — 报告输出模板

### scripts/
- `parse_document.py` — 文档解析与论断单元抽取
- `verify_sources.py` — 来源正确性与著录字段前置检查
- `apply_source_fixes.py` — 按核验结果生成字段修正 diff，确认后写回
- `fetch_metadata.py` — 元数据获取、验真、缓存
- `search_candidates.py` — 检索与初排
- `apply_replacement.py` — diff 生成、备份、确认后写回
- `rr_common.py` — 共享工具（规范化、缓存、HTTP、BM25 辅助）

## 版本记录

- v0.2.0：新增来源正确性前置检查与字段修正闭环；核验不通过时不得进入相关性评估。
- v0.1.1：题目+摘要降级模式；`title_only` 强制弃权，降级不得判 D。
- v0.1.0：解析、取数、检索、diff 脚本链与可选算法层。
