#!/usr/bin/env python3
"""
Mark WoW proper names as default ignored while preserving translation/note.

Heuristics (conservative):
- Candidate if translation casefold == word casefold OR word casefold == key (translation == word)
  AND original word contains uppercase letter or apostrophe, length >=3
  AND not in manually curated grammar overrides (we preserve curated notes)

Preserves existing status if already set; only adds ignored where missing.
Uses allowlist to avoid false positives on short common words.

Run after all audit waves.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CURATED = ROOT / "Data/CuratedDE.jsonl"
TRANSLATIONS = ROOT / "Data/cache/translations_de_en.jsonl"

# Keep these as common words even if same translation (avoid marking ignored)
COMMON_SAME_TRANSLATION_DENY = {
    "mama", "papa", "oma", "opa", "baby", "hotel", "hobby", "party", "fair", "cool", "tip",
}

PROPER_PATTERN = re.compile(r"^[A-ZÄÖÜ].*[A-Za-zÄÖÜäöüß'’\-]*$")

def is_proper_candidate(word: str, translation: str) -> bool:
    if len(word) < 3:
        return False
    if word.casefold() in COMMON_SAME_TRANSLATION_DENY:
        return False
    # translation == word (case-insensitive) is strongest signal for invariant WoW names
    if word.casefold() != translation.casefold():
        # Second signal: WoW fantasy pattern but translation differs (e.g., Sturmwind->Stormwind)
        # We only auto-mark these if curated already flagged? For now skip to avoid false positives.
        # Proper names with translated equivalents are handled via curated manual list; here we keep conservative.
        return False
    if not PROPER_PATTERN.match(word):
        return False
    # Must contain at least one uppercase letter (already) or apostrophe
    if word.islower():
        return False
    return True

def main():
    curated = {}
    for line in CURATED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        curated[r["key"]] = r

    # Load translations to get word form for entries not in curated
    trans_map = {json.loads(l)["key"]: json.loads(l) for l in TRANSLATIONS.read_text(encoding="utf-8").splitlines() if l.strip()}

    added = 0
    skipped_kept = 0
    for key, entry in curated.items():
        word = entry.get("word") or trans_map.get(key, {}).get("word") or key
        translation = entry.get("translation") or ""
        if entry.get("status") == "ignored":
            skipped_kept += 1
            continue
        if is_proper_candidate(word, translation):
            entry["status"] = "ignored"
            added += 1

    # Also consider non-curated entries that are proper names and have translation==word
    # They are not yet in CuratedDE, so we add them with status ignored preserving translation
    for key, rec in trans_map.items():
        if key in curated:
            continue
        word = rec.get("word") or key
        translation = rec.get("translation") or ""
        if not translation:
            continue
        if is_proper_candidate(word, translation):
            curated[key] = {"key": key, "word": word, "translation": translation, "note": rec.get("note") or "", "status": "ignored"}
            added += 1

    # Rewrite curated preserving order: existing order first, new proper names appended sorted
    # Keep original order for existing keys
    existing_order = []
    seen = set()
    for line in CURATED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        existing_order.append(r["key"])
        seen.add(r["key"])
    new_keys = [k for k in curated if k not in seen]
    # Also keys that were existing but now have status still keep order
    all_keys = existing_order + sorted(new_keys)
    CURATED.write_text("\n".join(json.dumps(curated[k], ensure_ascii=False, separators=(",", ":")) for k in all_keys) + "\n", encoding="utf-8")
    print(f"proper_names_marked={added} already_ignored={skipped_kept} curated_total={len(curated)}")

if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
