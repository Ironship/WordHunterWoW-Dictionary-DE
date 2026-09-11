#!/usr/bin/env python3
"""
Mark WoW proper names as default ignored while preserving translation/note.

Conservative batch (issue #1): candidate ONLY if ALL hold:
- word == translation (exact, case-sensitive, stripped)
- len(word) >= 3
- word.casefold() not in COMMON_SAME_TRANSLATION_DENY
- PROPER_PATTERN matches (starts with uppercase incl. AE/OE/UE)
- note contains "proper" (case-insensitive) -- curator-confirmed name

Translated-name pairs (Sturmwind->Stormwind) are never touched.
Existing status values are preserved; only missing status gains "ignored".

Operates on Data/CuratedDE.jsonl only (no Data/cache dependency -- cache
is gitignored and absent from clones). Preserves file order and JSON
formatting (separators ", "/": ", status appended last).

Run: python3 Tools/mark_proper_names.py [--check]
  --check: dry run, report only, exit 1 if anything would be marked.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CURATED = ROOT / "Data/CuratedDE.jsonl"

# Keep these as common words even if same translation (avoid marking ignored)
COMMON_SAME_TRANSLATION_DENY = {
    "mama", "papa", "oma", "opa", "baby", "hotel", "hobby", "party", "fair", "cool", "tip",
}

PROPER_PATTERN = re.compile(r"^[A-ZÄÖÜ].*[A-Za-zÄÖÜäöüß'’\-]*$")


def is_proper_candidate(word: str, translation: str, note: str) -> bool:
    if not word or not translation:
        return False
    translation = translation.strip()
    if word != translation:  # exact match only; casefold variants (Wolf/wolf) stay untouched
        return False
    if len(word) < 3:
        return False
    if word.casefold() in COMMON_SAME_TRANSLATION_DENY:
        return False
    if not PROPER_PATTERN.match(word):
        return False
    if "proper" not in (note or "").lower():  # curator confirmation gate
        return False
    return True


def main() -> int:
    check_only = "--check" in sys.argv
    lines = CURATED.read_text(encoding="utf-8").splitlines()
    out_lines = []
    added = 0
    already_ignored = 0
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        r = json.loads(line)
        if r.get("status") == "ignored":
            already_ignored += 1
            out_lines.append(line)
            continue
        if is_proper_candidate(r.get("word") or "", r.get("translation") or "", r.get("note") or ""):
            added += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        else:
            out_lines.append(line)
    if check_only:
        print(f"would_mark={added} already_ignored={already_ignored}")
        return 1 if added else 0
    CURATED.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"proper_names_marked={added} already_ignored={already_ignored} "
          f"curated_total={len(out_lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
