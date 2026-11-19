# reference-relevance

面向学术论文的引用相关性决策助手。先理解引用处的正文需求，再判断已引文献是否匹配；对低相关引用给出证据、建议动作与替换候选，默认只生成 diff，须人工确认后才写回原稿。

当前适用学科为经管实证与建模论文，支持 Word `.docx`、PDF、LaTeX，以及中文 GB/T 7714 与 APA 作者—年份制。

[English README](README_EN.md) · [参考文献与方法来源](REFERENCES.md)

## 功能

- 解析文档，抽取论断单元、引用位置、引用上下文与文献条目。
- 按「需求—供给」框架识别引用功能，逐条评估每位引用，不把同一括号内多篇文献共用一个判断。
- 多源获取真实摘要并交叉验真；中文来源单独路由，查不到时输出「无法核验」，不判定为文献不存在。
- 确定性评分、证据等级封顶、低置信度弃权；降级模式下不得直接判 D。
- 对低相关引用检索替换候选，生成 diff、备份与审计记录。

## 核心算法：如何判断引用是否相关

本项目的判断标准可以概括成一句话：**先看正文需要什么，再看文献能提供什么，最后看两者是否对得上**。单纯的标题或摘要相似度只是其中一个线索，不是最终结论。

1. **读懂引用处的正文需求。** 同一句话里的不同论断可能有不同需求：有的是理论依据，有的是方法来源，有的是数据来源，有的是与已有结果对比。项目按「功能轴 + 强度轴」记录需求：功能回答「为什么在这里引用」，强度回答「这里需要直接证据还是只需背景铺垫」。同一括号内多篇文献会被拆成多条独立评估。
2. **建立文献供给侧画像。** 使用真实摘要或原文证据，而不是把 BibTeX 条目当作摘要；同时记录文献类型、研究对象或样本、结论方向（支持 / 反驳 / 中性提及）、是否为一手来源等。结论方向为反驳时不能直接作为支持性供给。
3. **对齐评分与证据约束。** 评分分为三组：需求对齐（文献是否提供所需类型的证据）、支撑性（文献结论是否支持正文论断）、供给质量（证据强度、时效性、可核验性）。评分是加权计算，但有几条硬规则：反驳方向一票否决；论断先拆成可独立验证的最小单元；每条判断必须附正文句子与文献证据句；证据不足时置信度封顶并转人工，不强行判为错配。
4. **用同一把尺子找替换文献。** 只有当现有引用被判为低相关时，才检索替换候选。候选重排使用与评估相同的标准，因此不会出现「判它不合格、换上来的也不合格」的不一致。候选必须来自可核验的学术来源，并经人工确认后才可能写回。
5. **在证据不足时保守降级。** 当文献库额度不足、摘要不可得或中文来源无法核验时，默认只用题目与可得摘要做初判：置信度上限降低，不直接判 D，只标记「疑似不匹配，建议人工读原文」。NLI 与语义召回为可选算法层；依赖缺失时脚本显式标注降级结果，不会把退化结果伪装成模型判定。

更细的字段规范见 `references/rubric.md`，脚本接口与降级行为见 `references/algorithms.md`，参考文献与方法来源见 [REFERENCES.md](REFERENCES.md)。

## 安装

### WorkBuddy skill

```powershell
Copy-Item -Recurse -Force .\reference-relevance "$env:USERPROFILE\.workbuddy\skills\reference-relevant"
```

### 其他 agent

本项目按 `SKILL.md` 组织，可被支持 skill / agentskills 约定或能读取 Markdown 指令的 agent 使用。常见安装位置如下；具体路径以所用 agent 的文档为准。

| Agent | 常见安装方式 |
|---|---|
| Claude Code | 复制到 `~/.claude/skills/reference-relevant/` |
| Codex CLI | 复制到 `~/.codex/skills/reference-relevant/` |
| Gemini CLI | 复制到 `~/.gemini/skills/reference-relevant/` |
| Cursor | 复制 `SKILL.md` 内容到 `.cursor/rules/reference-relevant.mdc` |
| GitHub Copilot / 其他基于 `AGENTS.md` 的 agent | 将 `SKILL.md` 内容加入 `AGENTS.md` |

PowerShell 示例（先 `cd` 到本项目根目录）：

```powershell
# Claude Code
Copy-Item -Recurse -Force . "$env:USERPROFILE\.claude\skills\reference-relevant"

# Codex CLI
Copy-Item -Recurse -Force . "$env:USERPROFILE\.codex\skills\reference-relevant"

# Gemini CLI
Copy-Item -Recurse -Force . "$env:USERPROFILE\.gemini\skills\reference-relevant"
```

若 agent 需要显式触发，使用类似「用 reference-relevant 评估这段引用是否相关」的指令即可。

### 可选依赖

NLI 判定与语义召回需要额外依赖：

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
- 不在未告知用户的情况下向第三方服务上传稿件内容。

## 结构

```text
reference-relevance/
├── README.md                     # 中文主说明（本文件）
├── README_EN.md                  # 英文说明
├── REFERENCES.md                 # 方法依据与参考文献列表
├── SKILL.md                      # agent 工作流、脚本/agent 边界、人工确认闸门
├── LICENSE                       # MIT 许可
├── .gitignore                    # 忽略缓存、运行产物与本地配置
├── assets/
│   └── report-template.md        # Markdown 报告输出模板
├── references/
│   ├── algorithms.md             # 评分、NLI、语义召回、校准四个算法层脚本的接口与降级行为
│   ├── api-notes.md              # 英文数据源、限额、缓存、验真策略与字段说明
│   ├── citation_functions.md     # 经管实证/建模的引用功能分类体系与需求字段
│   ├── cn-sources.md             # 中文来源能力边界、题录比对方式与降级话术
│   └── rubric.md                 # 相关性评分量规：三组维度、四级判定、证据等级与置信度
└── scripts/
    ├── parse_document.py         # 解析 docx/pdf/LaTeX，抽取论断单元、引用位置与上下文
    ├── fetch_metadata.py         # 多源取摘要、验真、缓存，并生成供给画像基础字段
    ├── search_candidates.py      # BM25 词法召回替换候选
    ├── semantic_recall.py        # SPECTER2 语义重排；依赖缺失时回退 BM25
    ├── score_relevance.py        # 按 rubric 做确定性评分、否决、证据封顶与弃权
    ├── nli_verify.py             # 主张—证据三态判定，含原子 claim 拆分
    ├── calibrate.py              # ECE/Brier 与 Platt/Isotonic 置信度校准
    ├── apply_replacement.py      # 生成 diff、备份，并在显式确认后写回
    └── rr_common.py              # 规范化、缓存、HTTP 请求与 BM25 辅助函数
```

## 许可

MIT License，见仓库根目录 `LICENSE`。
