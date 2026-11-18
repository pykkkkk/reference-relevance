#!/usr/bin/env python3
"""Generate replacement diffs and apply only after explicit confirmation ."""
import argparse
import difflib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rr_common import read_json  # noqa: E402


def collect_text_files(input_path):
    p = Path(input_path)
    if p.is_dir():
        return sorted(list(p.glob("*.tex")) + list(p.glob("*.bib")))
    if p.suffix.lower() in (".tex", ".bib"):
        return [p]
    return []


def apply_actions(input_path, actions):
    files = collect_text_files(input_path)
    if not files:
        return {}, ["当前输入为 .docx/.pdf，当前版本不支持自动改写；请按 actions.json 手工调整，或改用 LaTeX 输入。"]
    originals = {f: f.read_text(encoding="utf-8", errors="ignore") for f in files}
    modified = dict(originals)
    warnings = []
    bib_target = next((f for f in files if f.suffix.lower() == ".bib"), None)
    appended = []
    for a in actions:
        act = a.get("action", {})
        if act.get("type") != "replace_citation":
            continue
        old, new = act.get("old_key"), act.get("new_key")
        bibtex = (act.get("replacement_bibtex") or "").strip()
        if not old or not new:
            warnings.append(f"{a.get('claim_id')}: 缺少 old_key/new_key，跳过自动替换")
            continue
        for f, text in list(modified.items()):
            if f.suffix.lower() != ".tex":
                continue  # 不改写 .bib 条目本身，避免把旧文献的元数据挂到新 key 上
            modified[f] = re.sub(r"(?<![A-Za-z0-9])" + re.escape(old) + r"(?![A-Za-z0-9])", new, text)
        entry_re = re.compile(r"@\w+\s*\{\s*" + re.escape(new) + r"\s*,", re.I)
        existing = "\n".join(v for k, v in modified.items() if k.suffix.lower() == ".bib")
        if bibtex and not entry_re.search(existing):
            appended.append(bibtex)
    if appended:
        if bib_target is None:
            bib_target = Path(input_path).parent / "replacement_entries.bib" if Path(input_path).is_file() else Path(input_path) / "replacement_entries.bib"
            modified[bib_target] = ""
            originals[bib_target] = ""
        modified[bib_target] = modified[bib_target].rstrip() + "\n\n" + "\n\n".join(appended) + "\n"
    return {"originals": originals, "modified": modified}, warnings


def make_diff(payload):
    chunks = []
    for f, before in payload["originals"].items():
        after = payload["modified"].get(f, before)
        if before == after:
            continue
        chunks.append("--- a/" + f.name)
        chunks.append("+++ b/" + f.name)
        chunks.extend(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
    return "\n".join(chunks) if chunks else "# No textual changes generated\n"


def main():
    ap = argparse.ArgumentParser(description="Generate replacement diff (never auto-apply without --apply)")
    ap.add_argument("--actions", default=".reference-relevant/actions.json")
    ap.add_argument("--input", required=True)
    ap.add_argument("-o", "--output", default=".reference-relevant/replacement.diff")
    ap.add_argument("--apply", action="store_true", help="显式确认后才写回，脚本会先备份")
    args = ap.parse_args()

    data = read_json(args.actions)
    actions = data.get("actions", data) if isinstance(data, dict) else data
    payload, warnings = apply_actions(args.input, actions)
    diff = make_diff(payload)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff, encoding="utf-8")
    for w in warnings:
        print("[apply] WARNING:", w, file=sys.stderr)

    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for f, before in payload["originals"].items():
            after = payload["modified"].get(f, before)
            if before == after:
                continue
            backup = f.with_name(f.name + f".bak.{stamp}")
            shutil.copy2(f, backup)
            f.write_text(after, encoding="utf-8")
            print(f"[apply] backed up -> {backup}")
            print(f"[apply] wrote -> {f}")
    else:
        print("[apply] diff only; original files untouched. Add --apply after user confirmation.")

    print(f"[apply] saved diff -> {out.resolve()}")


if __name__ == "__main__":
    main()
