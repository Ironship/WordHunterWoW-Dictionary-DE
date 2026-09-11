#!/usr/bin/env python3
"""
Mark WoW proper names as default ignored while preserving translation/note.

Conservative batches (issue #1). Every candidate must satisfy ALL base
predicates:
- word == translation (exact, case-sensitive, stripped)
- len(word) >= 3
- word.casefold() not in COMMON_SAME_TRANSLATION_DENY
- PROPER_PATTERN matches (starts with uppercase incl. AE/OE/UE)
- no existing status value (only missing status gains "ignored")

Plus ONE curator-confirmation gate:
- Batch 1: note contains "proper" (curator-confirmed name)
- Batch 2: note matches NPC/creature/place/faction keyword gates
  (NOTE_INCLUDE) without matching a safety exclusion (NOTE_EXCLUDE:
  part-of names, common nouns, loanwords, English common words,
  adjectives, meaning-glosses)

Translated-name pairs (Sturmwind->Stormwind) are never touched.
Empty-note rows are never auto-marked (German capitalizes all nouns).

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

# Keep these as common words even if same translation (avoid marking ignored).
# Extended in batch 2 (issue #1): English/loanword cognates and common nouns
# that pass word==translation must stay learnable, even if a note mentions
# npc/creature/place/faction.
COMMON_SAME_TRANSLATION_DENY = {
    "mama", "papa", "oma", "opa", "baby", "hotel", "hobby", "party", "fair", "cool", "tip",
    "computer", "video", "internet", "email", "laptop", "smartphone", "sport", "team",
    "job", "trend", "radio", "piano", "guitar", "jazz", "rock", "pop", "clip", "fan",
    "test", "citizen", "wash", "drop", "pool", "vendor", "trigger", "intro", "case",
    "farmer", "council", "swamp", "vale", "beach", "manor", "point", "hill", "high",
    "blade", "clans", "cabal", "huge", "classic", "maid", "scarlet", "paragon",
    "flowerpicker", "roc", "wyrm", "guts", "axe",
}

PROPER_PATTERN = re.compile(r"^[A-ZÄÖÜ].*[A-Za-zÄÖÜäöüß'’\-]*$")

# Batch 2: curator note keywords for NPC/creature/place/faction names.
NOTE_INCLUDE = re.compile(
    r"\bnpc\b|\bcreature\b|\bboss\b|\bbeast\b|\bmount\b"
    r"|\bplace\b|\bzone\b|\bcity\b|\btown\b|\bvillage\b"
    r"|\bfaction\b|\bclan\b|\btribe\b",
    re.IGNORECASE,
)

# Batch 2 safety exclusions: notes showing the word is really a common
# noun, a name fragment, or a glossed English word -- not a standalone name.
NOTE_EXCLUDE = re.compile(
    r"part of|common noun|loanword"
    r"|english\s+(word|compound|term|adjective)"
    r"|\badjective\b|\bmeans\b|\bmeaning\b",
    re.IGNORECASE,
)


def base_predicates(word: str, translation: str) -> bool:
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
    return True


def is_proper_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 1: curator wrote 'proper' in the note."""
    if not base_predicates(word, translation):
        return False
    if "proper" not in (note or "").lower():  # curator confirmation gate
        return False
    return True


def is_batch2_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 2: note names an NPC/creature/place/faction role for the entry."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False  # batch 1's domain; keep counts separate
    if not NOTE_INCLUDE.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def main() -> int:
    check_only = "--check" in sys.argv
    lines = CURATED.read_text(encoding="utf-8").splitlines()
    out_lines = []
    batch1 = 0
    batch2 = 0
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
        word = r.get("word") or ""
        translation = r.get("translation") or ""
        note = r.get("note") or ""
        if is_proper_candidate(word, translation, note):
            batch1 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        elif is_batch2_candidate(word, translation, note):
            batch2 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        else:
            out_lines.append(line)
    added = batch1 + batch2
    if check_only:
        print(f"would_mark={added} (batch1={batch1} batch2={batch2}) "
              f"already_ignored={already_ignored}")
        return 1 if added else 0
    CURATED.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"proper_names_marked={added} (batch1={batch1} batch2={batch2}) "
          f"already_ignored={already_ignored} curated_total={len(out_lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
