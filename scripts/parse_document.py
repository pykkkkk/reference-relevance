#!/usr/bin/env python3
"""Parse a paper into claim units, citation markers and reference entries (v0.1.0 skeleton)."""
import argparse
import itertools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import last_name, split_sentences, strip_latex, write_json  # noqa: E402


NUMBERED = re.compile(r"\[([\d\-–,\s]+)\]")
_CLAIM_SEQ = itertools.count(1)
PAREN = re.compile(r"\(\s*(?:e\.g\.\s*|eg\s*|i\.e\.\s*)?([A-Z][A-Za-z\.\-]*(?:\s+(?:et\s+al\.?|\\?&|and)\s*[A-Za-z\.\-]+)?)\s*,?\s*((?:19|20)\d{2}[a-z]?)\s*\)")
NARRATIVE = re.compile(r"([A-Z][A-Za-z\.\-]*(?:\s+(?:et\s+al\.?|\\?&|and)\s*[A-Za-z\.\-]+)?)\s+\(((?:19|20)\d{2}[a-z]?)\)")
GROUP = re.compile(r"\(([^()]*\b(?:19|20)\d{2}[^()]*)\)")
MULTI_ITEM = re.compile(r"([A-Z][A-Za-z\.\-]*(?:\s+(?:et\s+al\.?|\\?&|and)(?:\s+[A-Za-z\.\-]+)?)*)\s*,?\s*((?:19|20)\d{2}[a-z]?)")
YEAR = re.compile(r"(?:19|20)\d{2}")


def _ref_from_text(index, raw, key=None):
    raw = " ".join((raw or "").split())
    year_m = YEAR.search(raw)
    parts = [p.strip() for p in re.split(r"\.\s+", raw) if p.strip()]
    authors = parts[0] if parts else ""
    title = parts[1] if len(parts) > 1 else raw[:120]
    venue = parts[-1] if len(parts) > 2 else ""
    return {
        "index": index,
        "bib_key": key or f"ref{index}",
        "raw_text": raw,
        "title": title,
        "authors": authors,
        "year": year_m.group(0) if year_m else None,
        "venue": venue,
        "doi": "",
    }


def _parse_bib(content):
    refs = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", content, re.S | re.I):
        body = m.group(3)
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\"[^\"]*\")", body, re.S):
            val = f.group(2)
            val = val[1:-1] if val.startswith("{") and val.endswith("}") else val.strip('"')
            fields[f.group(1).lower()] = " ".join(val.split())
        raw = f"@{m.group(1)}{{{m.group(2)}, {body.strip()}}}"
        refs.append({
            "index": len(refs) + 1,
            "bib_key": m.group(2),
            "raw_text": raw,
            "title": fields.get("title", ""),
            "authors": fields.get("author", ""),
            "year": fields.get("year"),
            "venue": fields.get("journal") or fields.get("booktitle") or "",
            "doi": fields.get("doi", ""),
        })
    return refs


def _reference_section(blocks):
    out = []
    started = False
    for b in blocks:
        text = b["text"]
        if not started and re.search(r"参考文献|references|bibliography", text, re.I) and len(text) < 80:
            started = True
            continue
        if started and text.strip():
            out.append(text.strip())
    refs = []
    for line in out:
        m = re.match(r"^\[?(\d+)\]?[.、\s]\s*(.+)$", line)
        if m:
            refs.append(_ref_from_text(int(m.group(1)), m.group(2)))
        elif YEAR.search(line) and len(line) > 20:
            refs.append(_ref_from_text(len(refs) + 1, line))
    return refs


def parse_docx(path):
    try:
        from docx import Document
    except ImportError:
        raise SystemExit("缺少 python-docx，请先运行: pip install python-docx")
    doc = Document(str(path))
    blocks = [{"index": i + 1, "page": None, "text": p.text.strip()}
              for i, p in enumerate(doc.paragraphs) if p.text.strip()]
    return {"source_type": "docx", "blocks": blocks, "title": blocks[0]["text"] if blocks else ""}


def parse_pdf(path):
    try:
        import fitz
    except ImportError:
        raise SystemExit("缺少 PyMuPDF，请先运行: pip install PyMuPDF")
    doc = fitz.open(str(path))
    blocks = []
    for i, page in enumerate(doc):
        for j, line in enumerate(page.get_text().splitlines()):
            if line.strip():
                blocks.append({"index": len(blocks) + 1, "page": i + 1, "text": line.strip()})
    doc.close()
    return {"source_type": "pdf", "blocks": blocks, "title": ""}


def parse_tex(path):
    p = Path(path)
    directory = p if p.is_dir() else p.parent
    texs = list(directory.glob("*.tex")) if p.is_dir() else [p]
    main = next((t for t in texs if "\\begin{document}" in t.read_text(encoding="utf-8", errors="ignore")), texs[0] if texs else None)
    if main is None:
        raise SystemExit("未找到 .tex 文件")
    content = main.read_text(encoding="utf-8", errors="ignore")
    title_m = re.search(r"\\title\{([^}]*)\}", content)
    blocks = [{"index": i + 1, "page": None, "text": line.strip()}
              for i, line in enumerate(content.splitlines()) if line.strip()]
    refs = []
    for bib in directory.glob("*.bib"):
        refs.extend(_parse_bib(bib.read_text(encoding="utf-8", errors="ignore")))
    if not refs:
        refs = _parse_bib(content)
    return {"source_type": "latex", "blocks": blocks, "title": strip_latex(title_m.group(1)) if title_m else "", "bib_refs": refs}


def extract_claims(blocks, refs):
    by_key = {r["bib_key"]: r["index"] for r in refs}
    by_author_year = {}
    for r in refs:
        yr = (r["year"] or "")[:4]
        for part in re.split(r"\s+and\s+|\s*&\s*", r["authors"] or ""):
            ln = last_name(part)
            if ln:
                by_author_year.setdefault((ln, yr), r["index"])
    claims = []
    for b in blocks:
        text = b["text"]
        sents = split_sentences(text)
        group_spans = [m.span() for m in GROUP.finditer(text)
                       if len(YEAR.findall(m.group(1))) >= 2 or ";" in m.group(1)]
        for gspan in group_spans:
            inner = text[gspan[0] + 1:gspan[1] - 1]
            for mm in MULTI_ITEM.finditer(inner):
                author, year = mm.group(1).strip(), mm.group(2)[:4]
                idx = by_author_year.get((last_name(author), year))
                if idx is None:
                    idx = next((i for (a, y), i in by_author_year.items() if y == year and (a in last_name(author) or last_name(author) in a)), None)
                claims.append(_claim(b, sents, mm.group(0).strip(), [idx] if idx else [], "author_year_group", author, year, mm.start()))
        for m in NUMBERED.finditer(text):
            nums = [int(x) for x in re.split(r"[,，\s]+", m.group(1)) if x.isdigit()]
            claims.append(_claim(b, sents, m.group(0), nums, "numbered", match_pos=m.start()))
        for m in list(PAREN.finditer(text)) + list(NARRATIVE.finditer(text)):
            if any(gs <= m.start() and m.end() <= ge for gs, ge in group_spans):
                continue
            author, year = m.group(1), m.group(2)[:4]
            idx = by_author_year.get((last_name(author), year))
            if idx is None:
                idx = next((i for (a, y), i in by_author_year.items() if y == year and (a in last_name(author) or last_name(author) in a)), None)
            claims.append(_claim(b, sents, m.group(0), [idx] if idx else [], "author_year", author, year, m.start()))
    return claims


def _claim(block, sents, marker, indices, style, author="", year="", match_pos=None):
    hit = None
    if match_pos is not None:
        # 找覆盖该位置的句子，避免同一 marker 多次出现时都定位到第一处
        cursor = 0
        for s in sents:
            start = block["text"].find(s, cursor)
            if start >= 0 and start <= match_pos < start + len(s):
                hit = s
                break
            if start >= 0:
                cursor = start + len(s)
    if hit is None:
        hit = next((s for s in sents if marker in s), block["text"])
    pos = sents.index(hit) if hit in sents else 0
    return {
        "claim_id": f"c{next(_CLAIM_SEQ):03d}",
        "block_index": block["index"],
        "page": block.get("page"),
        "line": block["index"],
        "marker": marker,
        "style": style,
        "author_hint": author,
        "year_hint": year,
        "text": hit,
        "context_before": sents[pos - 1] if pos > 0 else "",
        "context_after": sents[pos + 1] if pos + 1 < len(sents) else "",
        "ref_indices": [i for i in indices if i],
    }


def main():
    ap = argparse.ArgumentParser(description="Parse paper into claim units and references")
    ap.add_argument("input", help=".docx / .pdf / .tex file or LaTeX project directory")
    ap.add_argument("-o", "--output", default=".reference-relevant/parsed.json")
    ap.add_argument("--discipline", choices=["econ-empirical", "econ-modeling"], default="econ-empirical")
    ap.add_argument("--rule-claims", action="store_true",
                    help="fallback: also extract claims by regex (default: only raw materials for LLM parsing)")
    args = ap.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")
    suffix = path.suffix.lower() if path.is_file() else "latex"
    if suffix == ".docx":
        parsed = parse_docx(path)
    elif suffix == ".pdf":
        parsed = parse_pdf(path)
    elif suffix in (".tex", ".latex", ".latexdir", "latex"):
        parsed = parse_tex(path)
    else:
        raise SystemExit(f"不支持的输入类型: {suffix}（支持 .docx / .pdf / .tex / LaTeX 目录）")

    refs = parsed.get("bib_refs") or _reference_section(parsed["blocks"])
    claims = extract_claims(parsed["blocks"], refs) if args.rule_claims else []
    method = "rule_based" if args.rule_claims else "llm"
    warnings = []
    if not refs:
        warnings.append("未解析到参考文献条目，请检查参考文献章节或 .bib 文件")
    if args.rule_claims and not claims:
        warnings.append("未解析到引用标记，中文全角括号或特殊宏可能需要人工核对")
    if not args.rule_claims:
        warnings.append("引用标记与功能分类需由大模型写入 claims；规则路径可用 --rule-claims 兜底")
    if suffix == ".pdf":
        warnings.append("PDF 解析为兜底路径，页码/行号与题录切分需人工抽检")

    out = {
        "source_type": parsed["source_type"],
        "discipline": args.discipline,
        "title": parsed["title"],
        "parsing_method": method,
        "reference_count": len(refs),
        "claim_count": len(claims),
        "references": refs,
        "claims": claims,
        "blocks": parsed["blocks"],
        "parse_warnings": warnings,
    }
    print(f"[parse] {len(refs)} refs, {len(claims)} citation units, {len(warnings)} warnings")
    write_json(args.output, out)
    print(f"[parse] saved -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
