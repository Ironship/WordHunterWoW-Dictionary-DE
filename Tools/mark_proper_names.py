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
- Batch 3: note matches character/location/dungeon/raid keyword gates
  (NOTE_INCLUDE3) without matching NOTE_EXCLUDE (batch-2 patterns plus
  uncertainty hedges: suggests/possibly/perhaps/unconfirmed/uncertain/
  maybe/likely). Same base predicates; title/quest/spell/item/ability/
  profession/pet/misc notes are out of scope until batch 4.
- Batch 4: note matches race gate (NOTE_INCLUDE4). Same base predicates;
  b1/b2/b3 domains excluded so counts stay separate. Surname/personal-name
  and invariant signals stay out until batch 5.
- Batch 5: note matches invariant gate (NOTE_INCLUDE5: untranslatable / do
  not translate / keep unchanged signals). Same base predicates; b1-b4
  domains excluded. Surname/personal-name slice stays out until batch 6.

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
# npc/creature/place/faction. Extended with batch-2 audit FPs (issue #1):
# generic English words, foods, fragments that slipped the note gates.
COMMON_SAME_TRANSLATION_DENY = {
    "mama", "papa", "oma", "opa", "baby", "hotel", "hobby", "party", "fair", "cool", "tip",
    "computer", "video", "internet", "email", "laptop", "smartphone", "sport", "team",
    "job", "trend", "radio", "piano", "guitar", "jazz", "rock", "pop", "clip", "fan",
    "test", "citizen", "wash", "drop", "pool", "vendor", "trigger", "intro", "case",
    "farmer", "council", "swamp", "vale", "beach", "manor", "point", "hill", "high",
    "blade", "clans", "cabal", "huge", "classic", "maid", "scarlet", "paragon",
    "flowerpicker", "roc", "wyrm", "guts", "axe",
    "blanches", "cheddar", "flight", "shady", "wardens", "bursters", "quagmire", "xylem",
    # Batch-3 audit FPs (issue #1): ranks, common human names, fragments,
    # technical markers, and item/vehicle/flora notes that passed the gate.
    "deprecated", "basteldings", "chevalier", "echelon", "korun", "shatter",
    "ella", "bill", "colin", "brownells", "flor", "zorts", "eggenmeiser",
    "blat", "rook",
    # Batch-4 audit FPs (issue #1): English senses of "race" (competition), not fantasy races.
    "intermediate", "multiplayer",
    # Batch-5 audit FPs (issue #1): placeholders/technical English, not names.
    "dnt", "unit-specified", "viewed",
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
# Extended in batch 3 (issue #1): uncertainty hedges are the main FP driver,
# plus possessive/plural forms, sounds/exclamations, titles, and glossed
# common nouns seen in the batch-3 audit.
NOTE_EXCLUDE = re.compile(
    r"part of|common noun|loanword|\bcompound\b|\+"
    r"|english\s+(word|compound|term|adjective|noun|name|location|treasure|source|dungeon)"
    r"|\badjective\b|\bmeans\b|\bmeaning\b|\bliterally\b|\betymology\b"
    r"|\bsuggests\b|\bpossibly\b|\bperhaps\b|\bunconfirmed\b"
    r"|\buncertain\b|\bmaybe\b|\blikely\b"
    r"|\bunable to confirm\b|\bcannot expand\b|\bnot confirmed\b"
    r"|\bpossessive\b|\bplural form\b|\bgenitive\b"
    r"|\babbreviation\b|\bacronym\b"
    r"|\bimperative\b|\binterjection\b|\bexclamation\b|\blaughter\b|\blaugh\b"
    r"|\bchuckle\b|\bdialogue\b|\bspeech\b|\bonomatopoeia\b|\bvocalization\b|\bsound-play\b"
    r"|\btitle\b|\bcommon human name\b|\barchaic\b|\bpoetic\b"
    r"|\bus spelling\b|\bsmall bed\b"
    r"|\bshortened title\b|\bare guardians\b|\bofficial .* term\b"
    r"|\btreasure\b|\bcontraction\b|\bevent label\b|\bcolor\b|\bmaterial\b"
    r"|\bprevents entry\b|\bloot until\b|\bboom-like\b|\bsound\b"
    r"|\bappears\b|\bpresumed\b|\benglish text\b",
    re.IGNORECASE,
)

# Batch 3: curator note keywords for character/location/dungeon/raid names.
NOTE_INCLUDE3 = re.compile(
    r"\bcharacter\b|\blocation\b|\bdungeon\b|\braid\b"
    r"|\binstance\b|\bcapital\b|\bsettlement\b|\bfortress\b|\bkeep\b|\boutpost\b",
    re.IGNORECASE,
)

# Batch 4: curator note keywords for race names.
NOTE_INCLUDE4 = re.compile(
    r"\brace\b",
    re.IGNORECASE,
)

# Batch 5: curator do-not-translate / invariant signals.
NOTE_INCLUDE5 = re.compile(
    r"untranslatable|not translatable|no translation needed"
    r"|keep unchanged|leave unchanged|do not translate"
    r"|not translated|remains the same|keep as is",
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


def is_batch3_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 3: note names a character/location/dungeon/raid role for the entry."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False  # batch 1's domain; keep counts separate
    if NOTE_INCLUDE.search(note or ""):
        return False  # batch 2's domain; keep counts separate
    if not NOTE_INCLUDE3.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def is_batch4_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 4: note names a race role for the entry."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False  # batch 1's domain; keep counts separate
    if NOTE_INCLUDE.search(note or ""):
        return False  # batch 2's domain; keep counts separate
    if NOTE_INCLUDE3.search(note or ""):
        return False  # batch 3's domain; keep counts separate
    if not NOTE_INCLUDE4.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def is_batch5_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 5: note says entry is invariant / do-not-translate."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False  # batch 1's domain
    if NOTE_INCLUDE.search(note or ""):
        return False  # batch 2's domain
    if NOTE_INCLUDE3.search(note or ""):
        return False  # batch 3's domain
    if NOTE_INCLUDE4.search(note or ""):
        return False  # batch 4's domain
    if re.search(r"\bsurname\b|\bpersonal name\b", note or "", re.IGNORECASE):
        return False  # batch 6's domain; keep counts separate
    if not NOTE_INCLUDE5.search(note or ""):
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
    batch3 = 0
    batch4 = 0
    batch5 = 0
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
        elif is_batch3_candidate(word, translation, note):
            batch3 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        elif is_batch4_candidate(word, translation, note):
            batch4 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        elif is_batch5_candidate(word, translation, note):
            batch5 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        else:
            out_lines.append(line)
    added = batch1 + batch2 + batch3 + batch4 + batch5
    if check_only:
        print(f"would_mark={added} (batch1={batch1} batch2={batch2} batch3={batch3} batch4={batch4} batch5={batch5}) "
              f"already_ignored={already_ignored}")
        return 1 if added else 0
    CURATED.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"proper_names_marked={added} (batch1={batch1} batch2={batch2} batch3={batch3} batch4={batch4} batch5={batch5}) "
          f"already_ignored={already_ignored} curated_total={len(out_lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
