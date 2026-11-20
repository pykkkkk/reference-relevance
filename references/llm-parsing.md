# 大模型引用解析规范

引用标记的识别与功能分类由大模型直接完成，规则解析器只作兜底。本文件定义大模型应如何读正文并写出 `parsed.json`。

## 输入

运行 `python scripts/parse_document.py <input> -o .reference-relevant/raw.json` 得到的原始材料：

- `references[]`：题录条目，含 `index`、`bib_key`、`title`、`authors`、`year`、`venue`、`doi`；
- `blocks[]`：带序号的正文块（每块是一段或一行）；
- `parse_warnings[]`：解析告警。

`.bib` / 参考文献章节的切分由脚本完成；**引用标记、引用归属、功能分类全部由大模型完成**。

## 输出：`parsed.json`

顶层字段：`source_type`、`discipline`、`title`、`parsing_method: "llm"`、`references`、`claims`、`parse_warnings`。

每个 `claim` 至少包含：

| 字段 | 含义 |
|---|---|
| `claim_id` | `c001`、`c002`……按文中出现顺序 |
| `block_index` | 来源正文块序号 |
| `marker` | 原文中的引用标记，如 `(Almond, 2006, Almond et al., 2007)` |
| `author_hint` / `year_hint` | 从标记中读出的作者与年份 |
| `text` | 标记所在的完整句子 |
| `context_before` / `context_after` | 相邻句，用于判断功能 |
| `ref_indices` | 该条引用对应的文献 index 列表；同一括号内多篇引用时**每篇一个 claim** |
| `function` | 引用功能，取自 `citation_functions.md` 的功能轴 |
| `strength` | `直接证据` / `间接背景` |
| `necessity` | `必须` / `建议` / `常识性可免引` |
| `confidence` / `needs_review` | 需求判断的置信度与是否需人工复核 |

## 必须遵守的解析规则

1. **一篇一议**：`(A, 2006, B, 2007, C, 2010)` 必须拆成 3 个 claim，每个 `ref_indices` 只含对应的一篇；不得整组共用一个功能判断。
2. **格式全覆盖**：作者—年份制含 `et al.`、`&`、`and`、`e.g.`、`i.e.`、`a la`、叙述式 `Harris and Todaro (1970)`；编号制含 `[1]`、`[1,2,3]`。
3. **多次出现分条**：同一文献在文中出现多次时，按出现位置分别生成 claim，各自绑定所在句子与功能。
4. **上下文定位**：以标记在原文中的实际位置确定所属句子，不要用「第一句包含该标记」的方式定位。
5. **原子化**：一句含多个可独立验证的论断且各有引用时，分别生成 claim；无引用的论断不生成 claim。
6. **功能先于文献**：根据正文表述判断需求，不从文献标题倒推功能。
7. **不确定就标注**：题名无法唯一映射到题录时，`ref_indices` 留空并写 `needs_review: true`，不要猜测。

## 兜底规则路径

无大模型可用时：

```bash
python scripts/parse_document.py <input> -o .reference-relevant/parsed.json --rule-claims
```

该路径输出中必须带 `parsing_method: "rule_based"`，并在报告中提示复杂引用格式（逗号分隔、`e.g.`、`a la`、多次出现、复杂 LaTeX 宏）可能漏检。
