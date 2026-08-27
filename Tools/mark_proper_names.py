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
NOISE_ROOTS = {"ah","ahh","ahhh","aaaa","aaaaa","aaaaah","oh","ohh","ohhh","uh","uhh","uhhh","hm","hmm","hmmm","ooh","wow","haha","hehe","ugh","mmm","ooo","aaa","huh"}

def is_proper_candidate(word: str, translation: str) -> bool:
    if len(word) < 3:
        return False
    if word.casefold() in COMMON_SAME_TRANSLATION_DENY:
        return False
    # translation == word (case-insensitive) is strongest signal for invariant WoW names
    if word.casefold() != translation.casefold():
        return False
    if not PROPER_PATTERN.match(word):
        return False
    if word.islower():
        return False
    return True

def is_noise_candidate(word: str) -> bool:
    w = word.strip()
    if len(w) < 3:
        return False
    low = w.casefold().replace("’","'").replace("—","").replace("–","")
    cleaned = re.sub(r"[^a-zäöüß]", "", low)
    if cleaned in NOISE_ROOTS:
        return True
    # 4+ same char in a row, e.g. AAAAAh, Uhhh, Hmmm
    if re.search(r"(.)\1{3,}", w):
        return True
    if re.search(r"(.)\1{3,}", cleaned):
        return True
    # stutter like A-a-aber already handled as proper? but also noise - keep conservative
    return False

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
        if is_proper_candidate(word, translation) or is_noise_candidate(word):
            entry["status"] = "ignored"
            added += 1

    for key, rec in trans_map.items():
        if key in curated:
            continue
        word = rec.get("word") or key
        translation = rec.get("translation") or ""
        if not translation:
            continue
        if is_proper_candidate(word, translation) or is_noise_candidate(word):
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
