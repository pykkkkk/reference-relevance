# reference-relevance

A citation-relevance decision assistant for academic writing. It first identifies what a citation is needed for in the surrounding text, then checks whether the cited work actually supplies it. Low-relevance citations receive evidence, recommended actions, and replacement candidates. Replacements are delivered as a diff by default and are written back only after explicit human confirmation.

The current discipline profile covers empirical and modeling papers in economics and management. Inputs include Word `.docx`, PDF, and LaTeX, with GB/T 7714 and APA author-year citation styles.

[中文 README](README.md) · [References and method sources](REFERENCES.md)

## Features

- Parse documents into claim units, citation positions, citation contexts, and reference entries.
- Use a need–supply framework to classify citation functions and assess each cited work individually, including every item inside a multi-citation parenthesis.
- Retrieve real abstracts from multiple sources and cross-check metadata; Chinese sources are routed separately, and unverifiable items are reported as "unverifiable" rather than "nonexistent".
- Apply deterministic scoring, evidence-level confidence caps, and abstention; degraded evidence never directly produces a mismatch verdict.
- Retrieve replacement candidates for low-relevance citations, generate diffs, backups, and an audit trail.

## Core algorithm: how relevance is judged

The criterion can be summarized in one sentence: **identify what the text needs, describe what the source supplies, and check whether they align**. Lexical or abstract similarity is only one signal, not the final decision.

1. **Read the citation context first.** Different claims in the same sentence may need different kinds of support: a theoretical basis, a method source, a data source, or a comparison with prior results. Each need is recorded on a functional axis and a strength axis: the functional axis asks why a citation is needed; the strength axis asks whether direct evidence or only background context is required. Multiple citations in one parenthesis are split into separate assessments.
2. **Build a supply profile.** Real abstracts or source passages are used instead of treating BibTeX entries as abstracts. The profile records evidence type, sample or research object, conclusion direction (support, refute, or neutral mention), and whether the source is primary. A refuting source cannot serve as direct support.
3. **Score alignment with evidence constraints.** The score has three groups: need alignment (whether the source provides the needed evidence type), support (whether the source conclusion supports the claim), and supply quality (evidence strength, timeliness, and verifiability). Several hard rules apply: refutation is vetoed; claims are split into independently verifiable atoms; every judgment includes both the citing sentence and a cited evidence sentence; and insufficient evidence caps confidence and triggers human review rather than a forced mismatch verdict.
4. **Use the same yardstick for replacement.** Replacement candidates are retrieved only when an existing citation is judged low-relevance. Candidates are reranked with the same criteria used for evaluation, avoiding the inconsistency of rejecting a citation and then recommending an equally weak replacement. Candidates must come from verifiable academic sources and are written back only after human confirmation.
5. **Degrade conservatively when evidence is thin.** When API quotas are exhausted, abstracts are unavailable, or Chinese sources cannot be verified, the tool performs a preliminary judgment using titles and available abstracts only: confidence is capped, no direct mismatch verdict is issued, and results are marked as "suspected mismatch, read the full text". NLI and semantic recall are optional algorithm layers; when dependencies are missing, scripts explicitly mark the degraded result rather than presenting it as a model judgment.

See `references/rubric.md` for field specifications, `references/algorithms.md` for script interfaces and degradation behavior, and [REFERENCES.md](REFERENCES.md) for the method sources.

## Installation

### WorkBuddy skill

```powershell
Copy-Item -Recurse -Force .\reference-relevance "$env:USERPROFILE\.workbuddy\skills\reference-relevant"
```

### Other agents

The project is organized around `SKILL.md` and can be used by agents that support skills / agentskills conventions or read Markdown instructions. Common locations are listed below; check the target agent documentation for exact paths.

| Agent | Common installation |
|---|---|
| Claude Code | Copy to `~/.claude/skills/reference-relevant/` |
| Codex CLI | Copy to `~/.codex/skills/reference-relevant/` |
| Gemini CLI | Copy to `~/.gemini/skills/reference-relevant/` |
| Cursor | Copy `SKILL.md` into `.cursor/rules/reference-relevant.mdc` |
| GitHub Copilot / other `AGENTS.md`-based agents | Add `SKILL.md` content to `AGENTS.md` |

PowerShell example (run from the project root):

```powershell
# Claude Code
Copy-Item -Recurse -Force . "$env:USERPROFILE\.claude\skills\reference-relevant"

# Codex CLI
Copy-Item -Recurse -Force . "$env:USERPROFILE\.codex\skills\reference-relevant"

# Gemini CLI
Copy-Item -Recurse -Force . "$env:USERPROFILE\.gemini\skills\reference-relevant"
```

If the agent requires explicit triggering, use an instruction such as "use reference-relevant to assess whether this citation is appropriate".

### Optional dependencies

NLI verification and semantic recall require:

```bash
pip install transformers torch sentence-transformers
```

Without them, the scorer and calibrator still run; NLI returns UNKNOWN and semantic recall falls back to BM25 with an explicit label.

## Usage

All intermediate files are written to `.reference-relevant/` under the working directory.

```bash
python scripts/parse_document.py <input> -o .reference-relevant/parsed.json --discipline econ-empirical
python scripts/fetch_metadata.py .reference-relevant/parsed.json -o .reference-relevant/supply.json
python scripts/score_relevance.py .reference-relevant/assessment.json -o .reference-relevant/scored.json
python scripts/search_candidates.py --assessment .reference-relevant/assessment.json -o .reference-relevant/candidates.json --top-k 5
python scripts/apply_replacement.py --actions .reference-relevant/actions.json --input <input> -o .reference-relevant/replacement.diff
```

## Data sources

English sources: Crossref, Semantic Scholar, OpenAlex. arXiv, dblp, and PubMed are excluded for economics and management.

Chinese sources: CNKI has no public API; captchas and anti-bot controls are not bypassed. Use exported bibliographic records or available connectors and compare author, title, year, and venue. See `references/cn-sources.md`.

## Scope and limitations

- Focuses on existing citations; uncited text is skipped except for high-risk concepts and central claims, where a "consider adding a citation" note may be produced.
- Does not replace dedicated reference verification or formatting tools, and does not make the final decision for the author.
- Replacements generate diffs by default; files are backed up and changed only after explicit confirmation.
- `abstract_only` evidence caps confidence at 0.6 and never yields a mismatch verdict directly; `title_only` caps it at 0.45 and forces abstention.
- Manuscript content is not uploaded to third-party services without the user's knowledge.

## Structure

```text
reference-relevance/
├── README.md                     # Chinese primary documentation
├── README_EN.md                  # English documentation
├── REFERENCES.md                 # Method sources and reference list
├── SKILL.md                      # Agent workflow, script/agent boundary, confirmation gate
├── LICENSE                       # MIT License
├── .gitignore                    # Ignore caches, runtime outputs, local config
├── assets/
│   └── report-template.md        # Markdown report template
├── references/
│   ├── algorithms.md             # Interfaces and degradation of scoring, NLI, semantic recall, calibration
│   ├── api-notes.md              # English data sources, limits, caching, verification, fields
│   ├── citation_functions.md     # Citation function taxonomy for empirical/modeling papers
│   ├── cn-sources.md             # Chinese source boundaries, record matching, fallback wording
│   └── rubric.md                 # Scoring rubric: dimensions, grades, evidence levels, confidence
└── scripts/
    ├── parse_document.py         # Parse docx/pdf/LaTeX into claims, citation positions, contexts
    ├── fetch_metadata.py         # Fetch abstracts, cross-check metadata, cache, build supply fields
    ├── search_candidates.py      # BM25 lexical recall of replacement candidates
    ├── semantic_recall.py        # SPECTER2 semantic reranking; BM25 fallback when unavailable
    ├── score_relevance.py        # Deterministic scoring, veto, evidence caps, abstention
    ├── nli_verify.py             # Three-way claim-evidence verification with atomic claim splitting
    ├── calibrate.py              # ECE/Brier and Platt/Isotonic confidence calibration
    ├── apply_replacement.py      # Generate diff, backup, apply only after confirmation
    └── rr_common.py              # Normalization, caching, HTTP requests, BM25 helpers
```

## License

MIT License. See `LICENSE`.
