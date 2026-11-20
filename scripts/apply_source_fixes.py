#!/usr/bin/env python3
"""Generate and apply bibliography corrections from source verification results."""
import argparse
import difflib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json  # noqa: E402


def entry_span(text, key):
    pattern = re.compile(r"@\w+\s*\{\s*" + re.escape(key) + r"\s*,.*?(?=\n@|\Z)", re.S | re.I)
    return pattern.search(text)


def build_diff(root, fixes):
    chunks = []
    prepared = {}
    for bib in sorted(root.rglob("*.bib")):
        text = bib.read_text(encoding="utf-8", errors="ignore")
        new = text
        for key, bibtex in fixes.items():
            m = entry_span(new, key)
            if not m:
                continue
            new = new[:m.start()] + bibtex.strip() + new[m.end():]
        if new != text:
            prepared[bib] = (text, new)
            chunks.append(f"--- a/{bib.name}")
            chunks.append(f"+++ b/{bib.name}")
            chunks.extend(difflib.unified_diff(text.splitlines(), new.splitlines(), lineterm=""))
    return "\n".join(chunks) if chunks else "# No automatic corrections generated\n", prepared


def main():
    ap = argparse.ArgumentParser(description="Apply verified bibliography corrections")
    ap.add_argument("check", help="source_check.json from verify_sources.py")
    ap.add_argument("--input", required=True, help="Input file or directory containing .bib")
    ap.add_argument("-o", "--output", default=".reference-relevant/source_fixes.diff")
    ap.add_argument("--apply", action="store_true", help="write changes after backup; never automatic")
    args = ap.parse_args()

    data = read_json(args.check)
    fixes, refused = {}, []
    for it in data.get("items", []):
        if it.get("status") == "fabricated_suspected":
            refused.append(it.get("bib_key") or it.get("ref_index"))
        elif it.get("status") == "needs_fix" and it.get("suggested_bibtex"):
            fixes[it["bib_key"]] = it["suggested_bibtex"]
    diff, prepared = build_diff(Path(args.input), fixes)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff, encoding="utf-8")

    if refused:
        print("[fix] 以下条目疑似不存在，不得自动改写，须人工确认：" + ", ".join(map(str, refused)), file=sys.stderr)
    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path, (_, new) in prepared.items():
            backup = path.with_name(path.name + f".bak.{stamp}")
            shutil.copy2(path, backup)
            path.write_text(new, encoding="utf-8")
            print(f"[fix] backup -> {backup}")
            print(f"[fix] wrote -> {path}")
    else:
        print("[fix] diff only; original files untouched. Add --apply after confirmation.")
    print(f"[fix] saved diff -> {out.resolve()}")


if __name__ == "__main__":
    main()
