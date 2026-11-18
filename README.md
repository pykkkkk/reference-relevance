# reference-relevant

面向学术论文的引用相关性决策助手。先理解引用处的正文需求，再判断已引文献是否匹配；对低相关引用给出证据、建议动作与替换候选，默认只生成 diff，须人工确认后才写回原稿。

当前适用学科为经管实证与建模论文，支持 Word `.docx`、PDF、LaTeX，以及中文 GB/T 7714 与 APA 作者—年份制。

## 功能

- 解析文档，抽取论断单元、引用位置、引用上下文与文献条目。
- 按「需求—供给」框架识别引用功能，逐条评估每位引用，不把同一括号内多篇文献共用一个判断。
- 多源获取真实摘要并交叉验真；中文来源单独路由，查不到时输出「无法核验」，不判定为文献不存在。
- 确定性评分、证据等级封顶、低置信度弃权；降级模式下不得直接判 D。
- 对低相关引用检索替换候选，生成 diff、备份与审计记录。

## 安装

作为 WorkBuddy skill 使用：

```powershell
Copy-Item -Recurse -Force .\reference-relevance "$env:USERPROFILE\.workbuddy\skills\reference-relevant"
```

可选依赖（NLI 判定与语义召回需要）：

```bash
pip install transformers torch sentence-transformers
```

未安装时，评分器与校准器仍可运行；NLI 输出 UNKNOWN，语义召回回退 BM25 并显式标注。

## 使用

所有中间产物写入运行目录下的 `.reference-relevant/`，不污染原稿目录。

```bash
python scripts/parse_document.py <input> -o .reference-relevant/parsed.json --discipline econ-empirical
python scripts/fetch_metadata.py .reference-relevant/parsed.json -o .reference-relevant/supply.json
python scripts/score_relevance.py .reference-relevant/assessment.json -o .reference-relevant/scored.json
python scripts/search_candidates.py --assessment .reference-relevant/assessment.json -o .reference-relevant/candidates.json --top-k 5
python scripts/apply_replacement.py --actions .reference-relevant/actions.json --input <input> -o .reference-relevant/replacement.diff
```

详细工作流与字段规范见 `SKILL.md`；算法脚本的接口与降级行为见 `references/algorithms.md`；评分量规见 `references/rubric.md`。

## 数据源

英文来源：Crossref、Semantic Scholar、OpenAlex。经管场景不纳入 arXiv、dblp、PubMed。

中文来源：CNKI 无公开 API；不绕过验证码或反爬。可通过题录导出或可用连接器获取，按「作者 + 题名 + 年份 + 刊名」四字段比对。详见 `references/cn-sources.md`。

## 边界与限制

- 主攻已有引用；无引用区域默认不检查，仅对重要概念与核心论断做「建议补引」提醒。
- 不以文献验真或格式规范检查为主，也不替代作者做最终决定。
- 替换默认只生成 diff，须显式确认并先备份原文件。
- 证据等级为 `abstract_only` 时置信度上限 0.6，不得直接判 D；`title_only` 时上限 0.45 并强制弃权。
- 未发表稿件尽量本地处理，不在未告知用户的情况下上传第三方服务。

## 结构

```text
reference-relevance/
├── SKILL.md
├── references/
│   ├── algorithms.md
│   ├── api-notes.md
│   ├── citation_functions.md
│   ├── cn-sources.md
│   └── rubric.md
├── scripts/
│   ├── apply_replacement.py
│   ├── calibrate.py
│   ├── fetch_metadata.py
│   ├── nli_verify.py
│   ├── parse_document.py
│   ├── rr_common.py
│   ├── score_relevance.py
│   ├── search_candidates.py
│   └── semantic_recall.py
└── assets/
    └── report-template.md
```

## 许可

MIT License，见仓库根目录 `LICENSE`。
