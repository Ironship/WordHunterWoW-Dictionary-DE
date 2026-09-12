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
- Batch 6: note matches surname/personal-name gate (NOTE_INCLUDE6). Same
  base predicates; b1-b5 domains excluded. Demon/god/deity and
  king/queen/lord slices stay out until batch 7.
- Batch 7: note matches demon/god/deity/loa gate (NOTE_INCLUDE7). Same
  base predicates; b1-b6 domains excluded. King/queen/lord slice stays
  out until batch 8.
- Batch 8: note matches king/queen/lord/prince gate (NOTE_INCLUDE8). Same
  base predicates; b1-b7 domains excluded.

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
LUA = ROOT / "Data/DictionaryDE.lua"
EXPECTED_LUA_CHUNKS = 6

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
    # Batch-6 audit FP (issue #1): bird species, not a name.
    "kestrel",
    # Batch-7 audit FPs (issue #1): item type and plural monster type, not names.
    "aldrachi", "infernals",
    # Batch-8 audit FPs (issue #1): common noun / creature type, not names.
    "king", "val'kyr",
    # Manual curator passes 20: fragments/generics kept learnable.
    "god", "titan", "run", "song", "broken", "highlands",
    "foothills", "glades", "booty", "harbor", "gorge", "grotto",
    # Audit 30-50: materials + inflected plurals, not standalone names.
    "argunite", "azerite", "vol'jins", "saurfangs", "dar'guds",
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

# Batch 6: curator surname / personal-name signals.
NOTE_INCLUDE6 = re.compile(
    r"\bsurname\b|\bpersonal name\b",
    re.IGNORECASE,
)

# Batch 7: curator demon/god/deity/loa signals.
NOTE_INCLUDE7 = re.compile(
    r"\bdemon\b|\bgod\b|\bdeity\b|\bloa\b",
    re.IGNORECASE,
)

# Batch 8: curator king/queen/lord/prince signals.
NOTE_INCLUDE8 = re.compile(
    r"\bking\b|\bqueen\b|\blord\b|\bprince\b",
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


def is_batch6_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 6: note says entry is a surname / personal name."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False
    if NOTE_INCLUDE.search(note or ""):
        return False
    if NOTE_INCLUDE3.search(note or ""):
        return False
    if NOTE_INCLUDE4.search(note or ""):
        return False
    if NOTE_INCLUDE5.search(note or ""):
        return False
    if not NOTE_INCLUDE6.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def is_batch7_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 7: note says entry is a demon/god/deity/loa name."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False
    if NOTE_INCLUDE.search(note or ""):
        return False
    if NOTE_INCLUDE3.search(note or ""):
        return False
    if NOTE_INCLUDE4.search(note or ""):
        return False
    if NOTE_INCLUDE5.search(note or ""):
        return False
    if NOTE_INCLUDE6.search(note or ""):
        return False
    if not NOTE_INCLUDE7.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def is_batch8_candidate(word: str, translation: str, note: str) -> bool:
    """Batch 8: note says entry is a king/queen/lord/prince name."""
    if not base_predicates(word, translation):
        return False
    if "proper" in (note or "").lower():
        return False
    if NOTE_INCLUDE.search(note or ""):
        return False
    if NOTE_INCLUDE3.search(note or ""):
        return False
    if NOTE_INCLUDE4.search(note or ""):
        return False
    if NOTE_INCLUDE5.search(note or ""):
        return False
    if NOTE_INCLUDE6.search(note or ""):
        return False
    if NOTE_INCLUDE7.search(note or ""):
        return False
    if not NOTE_INCLUDE8.search(note or ""):
        return False
    if NOTE_EXCLUDE.search(note or ""):
        return False
    return True


def parse_lua_rows():
    """Parse DictionaryDE.lua rows: returns (lua_rows set, lua_ignored set, chunks int).

    Robust key parse handling \\" and \\\\ escapes (k'arroc, kaz'jatar).
    Never inserts rows; read-only for --check parity.
    """
    import re as _re
    pat = _re.compile(r'WordHunterWoW_Dictionary_DE\["((?:\\.|[^"\\])*)"\]')
    def _unescape(s: str) -> str:
        out = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == "\\" and i + 1 < len(s):
                n = s[i + 1]
                if n == "n":
                    out.append("\n")
                elif n == "r":
                    out.append("\r")
                else:
                    out.append(n)
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)
    rows = set()
    ignored = set()
    chunks = 0
    try:
        text = LUA.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows, ignored, chunks
    for line in text:
        if line == ";(function()":
            chunks += 1
            continue
        if not line.startswith("WordHunterWoW_Dictionary_DE["):
            continue
        m = pat.search(line)
        if not m:
            continue
        k = _unescape(m.group(1))
        rows.add(k)
        if 'status = "ignored"' in line:
            ignored.add(k)
    return rows, ignored, chunks


def sync_lua_status(curated_ignored: set) -> int:
    """In-place Lua status sync: add status to EXISTING rows only.

    Never inserts new rows (the curated-ignored-not-in-Lua gap is the
    build filter english_leftover/cyrillic, not a sync target).
    Preserves chunk wrappers and line count. Returns rows updated.
    """
    if not LUA.exists():
        return 0
    lines = LUA.read_text(encoding="utf-8").splitlines()
    import re as _re
    pat = _re.compile(r'WordHunterWoW_Dictionary_DE\["((?:\\.|[^"\\])*)"\]')
    def _unescape(s: str) -> str:
        out = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == "\\" and i + 1 < len(s):
                n = s[i + 1]
                if n == "n":
                    out.append("\n")
                elif n == "r":
                    out.append("\r")
                else:
                    out.append(n)
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)
    updated = 0
    out = []
    for line in lines:
        if line.startswith("WordHunterWoW_Dictionary_DE[") and 'status = "ignored"' not in line:
            m = pat.search(line)
            if m and _unescape(m.group(1)) in curated_ignored:
                line = line.rstrip()
                assert line.endswith(" }")
                line = line[:-2] + ', status = "ignored" }'
                updated += 1
        out.append(line)
    if updated:
        LUA.write_text("\n".join(out) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    check_only = "--check" in sys.argv
    lines = CURATED.read_text(encoding="utf-8").splitlines()
    out_lines = []
    batch1 = 0
    batch2 = 0
    batch3 = 0
    batch4 = 0
    batch5 = 0
    batch6 = 0
    batch7 = 0
    batch8 = 0
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
        elif is_batch6_candidate(word, translation, note):
            batch6 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        elif is_batch7_candidate(word, translation, note):
            batch7 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        elif is_batch8_candidate(word, translation, note):
            batch8 += 1
            if check_only:
                out_lines.append(line)
            else:
                r["status"] = "ignored"  # appended last, order preserved
                out_lines.append(json.dumps(r, ensure_ascii=False))
        else:
            out_lines.append(line)
    added = batch1 + batch2 + batch3 + batch4 + batch5 + batch6 + batch7 + batch8
    # Hardened parity (issue #1 follow-up): curated<->Lua status must agree on
    # shared keys. The curated-ignored-not-in-Lua gap is the build filter
    # (english_leftover/cyrillic in build_dictionary_lua.py), reported not failed.
    curated_ignored_keys = set()
    for _line in lines:
        if not _line.strip():
            continue
        try:
            _r = json.loads(_line)
        except Exception:
            continue
        if _r.get("status") == "ignored" and _r.get("key"):
            curated_ignored_keys.add(_r["key"])
    lua_rows, lua_ignored, lua_chunks = parse_lua_rows()
    missing_from_lua = curated_ignored_keys - lua_rows
    in_lua_no_status = (curated_ignored_keys & lua_rows) - lua_ignored
    lua_not_in_cur = lua_ignored - curated_ignored_keys
    deny_violations = 0
    for _line in lines:
        if not _line.strip():
            continue
        _r = json.loads(_line)
        if _r.get("status") == "ignored":
            _w = (_r.get("word") or "").casefold()
            if _w in COMMON_SAME_TRANSLATION_DENY:
                deny_violations += 1
    if check_only:
        print(f"would_mark={added} (batch1={batch1} batch2={batch2} batch3={batch3} batch4={batch4} batch5={batch5} batch6={batch6} batch7={batch7} batch8={batch8}) "
              f"already_ignored={already_ignored}")
        print(f"lua_chunks={lua_chunks} (expected={EXPECTED_LUA_CHUNKS}) "
              f"lua_rows={len(lua_rows)} lua_ignored={len(lua_ignored)} "
              f"missing_from_lua={len(missing_from_lua)} "
              f"in_lua_no_status={len(in_lua_no_status)} "
              f"lua_not_in_cur={len(lua_not_in_cur)} "
              f"deny_violations={deny_violations}")
        fail = False
        if added:
            fail = True
        if lua_chunks != EXPECTED_LUA_CHUNKS:
            fail = True
        if in_lua_no_status:
            fail = True
        if lua_not_in_cur:
            fail = True
        if deny_violations:
            fail = True
        return 1 if fail else 0
    CURATED.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    # In-place Lua status sync for existing rows only (no cache needed).
    # Recompute ignored set including newly marked rows.
    new_ignored = set(curated_ignored_keys)
    for _line in out_lines:
        if not _line.strip():
            continue
        _r = json.loads(_line)
        if _r.get("status") == "ignored" and _r.get("key"):
            new_ignored.add(_r["key"])
    lua_updated = sync_lua_status(new_ignored)
    print(f"proper_names_marked={added} (batch1={batch1} batch2={batch2} batch3={batch3} batch4={batch4} batch5={batch5} batch6={batch6} batch7={batch7} batch8={batch8}) "
          f"already_ignored={already_ignored} curated_total={len(out_lines)} lua_updated={lua_updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
