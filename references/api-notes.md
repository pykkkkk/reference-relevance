# 数据源与验真注意事项

## 英文数据源

| 来源 | 用途 | 限制与礼节 |
|---|---|---|
| Crossref | DOI / 标题解析、元数据、年份与期刊校验 | 加 `mailto` 进 polite pool；约 50 req/s |
| Semantic Scholar | 摘要、引用关系、领域标签 | 免费约 100 req/5min；摘要可能缺失 |
| OpenAlex | 广覆盖检索、semantic search | 免费额度按调用计费；`per_page=100` 更省；摘要为倒排索引需重建 |

**经管场景不纳入**：arXiv、dblp、PubMed（覆盖几乎无关）。

## 中文数据源

见 `cn-sources.md`。中文来源单独路由，不与英文混用同一条查询链。

## 验真算法（fetch_metadata.py 实现）

1. **DOI / ID 优先**：有 DOI 时直接按 DOI 取记录，不按标题模糊搜。
2. **多源交叉**：至少两个来源命中才记 `verified`；单源命中记 `weak_verified`。
3. **防假匹配**：
   - 标题相似度（Jaccard，去停用词）≥ 0.5；
   - 第一作者姓氏重叠；
   - 年份差 > 2 年记 warning，不直接否决（可能是版本差异）。
4. **不取首条即信**：Semantic Scholar / OpenAlex / dblp 等多候选源必须逐条打分后选最佳。
5. **禁止弱兜底**：不得用「网页里出现 ≥2 个标题词」判定文献存在。WebSearch 只能作人工复核线索。
6. **中文四字段比对**：作者 + 题名 + 年份 + 刊名，缺一记 `partial_match`。

## 缓存

- 目录：`.reference-relevant/cache/`
- 键：来源 + 规范化查询串的 SHA-256 前 16 位
- 默认 TTL：7 天；验真结果可长期缓存，摘要按 30 天刷新
- 每次请求带 User-Agent 与 `mailto`，遇 429 指数退避

## 摘要使用纪律

- 主题与支撑性判断必须使用**真实摘要或全文**，不得用 BibTeX raw text 充当摘要（CiteCheck 的已知缺陷）。
- 摘要不可得：`source_unreachable`，仅做题名级判断，置信度上限 0.5。
- 中文文献核验失败：`unverifiable_zh`，不做 D 级判定。

## 输出字段（supply.json）

```json
{
  "ref_index": 7,
  "title": "…",
  "year": "2019",
  "venue": "…",
  "doi": "…",
  "abstract": "真实摘要",
  "abstract_source": "SemanticScholar",
  "verification": "verified|weak_verified|unverifiable_zh|not_found",
  "warnings": ["year mismatch"],
  "supply_profile": {
    "evidence_type": "准实验/DID",
    "sample": "中国上市公司 2008–2020",
    "direction_hint": "SUPPORT|REFUTE|NEUTRAL|UNKNOWN",
    "source_layer": "一手|综述|转引",
    "timeliness": "经典|适中|过时"
  }
}
```
