# reference-relevance

A citation-relevance decision assistant for academic writing. It first verifies that each cited work exists and that its bibliographic details are correct. It then identifies what a citation is needed for in the surrounding text and checks whether the cited work actually supplies it. Low-relevance citations receive evidence, recommended actions, and replacement candidates. Replacements are delivered as a diff by default and are written back only after explicit human confirmation.

The current discipline profile covers empirical and modeling papers in economics and management. Inputs include Word `.docx`, PDF, and LaTeX, with GB/T 7714 and APA author-year citation styles.

[中文 README](README.md) · [References and method sources](REFERENCES.md)

## Features

- Pre-flight source verification: check existence and compare authors, title, venue, year, DOI, volume, issue, and pages against trusted databases; correct errors before evaluating relevance.
- Parse documents into claim units, citation positions, citation contexts, and reference entries.
- Use a need–supply framework to classify citation functions and assess each cited work individually, including every item inside a multi-citation parenthesis.
- Retrieve real abstracts from multiple sources and cross-check metadata; Chinese sources are routed separately, and unverifiable items are reported as "unverifiable" rather than "nonexistent".
- Apply deterministic scoring, evidence-level confidence caps, and abstention; degraded evidence never directly produces a mismatch verdict.
- Retrieve replacement candidates for low-relevance citations, generate diffs, backups, and an audit trail.

## Core algorithm: how relevance is judged

The criterion can be summarized in one sentence: **identify what the text needs, describe what the source supplies, and check whether they align**. Lexical or abstract similarity is only one signal, not the final decision.

The workflow has six stages. Each solves a concrete problem and has a script or model behind it:

| Stage | What you see | What happens underneath |
|---|---|---|
| 0. Source correctness | Whether the work exists and needs bibliographic correction | `verify_sources.py` queries Crossref and OpenAlex by DOI or title and compares authors, title, venue, year, DOI, volume, issue, and pages; `apply_source_fixes.py` produces a correction diff |
| 1. Need profile | What job each citation is doing | Two templates (empirical / modeling) classify functions such as theory, method, data/measurement, and result comparison, plus evidence strength; multiple citations in one parenthesis are split |
| 2. Supply profile | What the source actually supplies | `fetch_metadata.py` retrieves real abstracts and cross-checks metadata; an NLI model labels the conclusion as support, refute, or neutral mention; refutation cannot be used as support |
| 3. Alignment scoring | An A / B / C / D verdict | `score_relevance.py` computes a weighted score over three groups; claims are split into atoms and checked separately; both the citing sentence and a cited evidence sentence are recorded |
| 4. Replacement candidates | Better alternatives with reasons | `search_candidates.py` performs BM25 lexical recall and `semantic_recall.py` reranks with SPECTER embeddings; candidates are scored with **the same criteria** used for the original citation |
| 5. Decision and write-back | A diff, a backup, and a confirmation gate | `apply_replacement.py` generates a diff by default and writes only after explicit confirmation; `calibrate.py` can calibrate confidence when human labels exist |

### Four design choices that matter to users

1. **Need comes before source.** We read the text first, then ask whether the source supplies it. This separates a legitimate background citation from a topically related source that cannot support the claim.
2. **One yardstick.** Evaluation and replacement ranking use the same scoring criteria, avoiding the inconsistency of rejecting a citation and then recommending an equally weak replacement.
3. **No conclusion without evidence.** Abstract-level evidence caps confidence; title-level evidence is escalated to a human; unverifiable Chinese sources are reported as unverifiable, not nonexistent.
4. **No silent rewriting.** Replacements are delivered as diffs and written only after explicit confirmation; academic responsibility stays with the author.

### Implementation parameters (for review and tuning)

| Component | Key settings |
|---|---|
| Source check | Title similarity threshold 0.6; venue similarity 0.35; year difference over 2 years is a field error; no matches produce `fabricated_suspected` or `unverifiable_*`, never an automatic fabrication verdict |
| Scoring weights | Need alignment 0.40 (function 0.25 + object 0.15); support 0.40 (claim support 0.30 + direction 0.10); supply quality 0.20 (evidence strength 0.10 + timeliness 0.05 + primary/verifiable 0.05) |
| Grades | A ≥ 0.85; B 0.65–0.85; C 0.40–0.65; D < 0.40; REFUTE direction is a veto |
| Evidence caps | `full_text` 1.0; `abstract_only` 0.6; `title_only` 0.45; `unverifiable` 0.3. Low confidence always abstains to human review |
| NLI | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, three states SUPPORT / REFUTE / NEUTRAL with probabilities; missing dependencies return UNKNOWN and fall back to agent reasoning |
| Semantic recall | `sentence-transformers/allenai-specter` (SPECTER) dual-encoder cosine reranking; fallback to BM25 (k1=1.5, b=0.75) with `lexical_fallback` when unavailable |
| Calibration | numpy-only ECE, Brier Score, Platt Scaling, and Isotonic Regression; no sklearn dependency |
| Model access | NLI and semantic recall are optional layers; in some regions set `HF_ENDPOINT=https://hf-mirror.com`; degraded results are always labeled explicitly and never presented as model judgments |

See `references/rubric.md` for field specifications, `references/source-verification.md` for source checks, `references/algorithms.md` for script interfaces and degradation behavior, and [REFERENCES.md](REFERENCES.md) for the method sources.

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
python scripts/verify_sources.py .reference-relevant/parsed.json -o .reference-relevant/source_check.json
python scripts/apply_source_fixes.py .reference-relevant/source_check.json --input <input> -o .reference-relevant/source_fixes.diff
python scripts/fetch_metadata.py .reference-relevant/parsed.json -o .reference-relevant/supply.json
python scripts/score_relevance.py .reference-relevant/assessment.json -o .reference-relevant/scored.json
python scripts/search_candidates.py --assessment .reference-relevant/assessment.json -o .reference-relevant/candidates.json --top-k 5
python scripts/apply_replacement.py --actions .reference-relevant/actions.json --input <input> -o .reference-relevant/replacement.diff
```

## Data sources

English sources: Crossref, Semantic Scholar, OpenAlex. arXiv, dblp, and PubMed are excluded for economics and management.

Chinese sources: CNKI has no public API; captchas and anti-bot controls are not bypassed. Use exported bibliographic records or available connectors and compare author, title, year, and venue. See `references/cn-sources.md`.

## Scope and limitations

- Focuses on existing citations and verifies source correctness before relevance assessment; uncited text is skipped except for high-risk concepts and central claims.
- Source verification is not a comprehensive formatting audit and does not replace author confirmation; unverifiable sources are reported as such, not as nonexistent.
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
│   ├── rubric.md                 # Scoring rubric: dimensions, grades, evidence levels, confidence
│   └── source-verification.md    # Source check fields, statuses, and handling order
└── scripts/
    ├── parse_document.py         # Parse docx/pdf/LaTeX into claims, citation positions, contexts
    ├── verify_sources.py         # Pre-flight existence and metadata verification
    ├── apply_source_fixes.py     # Generate reviewed metadata correction diffs and apply on confirmation
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
