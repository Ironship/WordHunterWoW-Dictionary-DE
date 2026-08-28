#!/usr/bin/env python3
"""Flag entries whose German carries a WoW lore stem the English fails to honour.

The original candidate heuristics missed a whole class: Hoellenhorde came
through as "Hellhorde" when the German Hoellen- is the game's own rendering of
Fel, so the English should read Fel Horde. These are single words, correctly
formed and plausibly translated, so no length or compound test catches them.
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRANS = ROOT / "Data/cache/translations_de_en.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
OUT = ROOT / "Data/cache/lore_candidates.jsonl"

# German stem -> the English WoW uses. A hit means the German stem is present
# and none of the expected English forms appear in the translation.
STEMS = {
    "höllen": ["fel"],
    "geißel": ["scourge"],
    "zwielicht": ["twilight"],
    "schattenhammer": ["twilight's hammer"],
    "dunkeleisen": ["dark iron"],
    "sturmwind": ["stormwind"],
    "eisenschmiede": ["ironforge"],
    "unterstadt": ["undercity"],
    "donnerfels": ["thunder bluff"],
    "eisenkrallen": ["ironclaw"],
    "brennende legion": ["burning legion"],
    "scherbenwelt": ["outland"],
    "nordend": ["northrend"],
    "pandaria": ["pandaria"],
    "drachenseele": ["dragon soul"],
    "lichkönig": ["lich king"],
    "verlassene": ["forsaken"],
    "blutelf": ["blood elf"],
    "nachtelf": ["night elf"],
    "draenei": ["draenei"],
    "worgen": ["worgen"],
    "goblin": ["goblin"],
    "vrykul": ["vrykul"],
    "naaru": ["naaru"],
    "arkan": ["arcane"],
    "leere": ["void"],
    "seelenschmied": ["soulforge"],
    "lichtgeschmiedet": ["lightforged"],
    "sonnenbrunnen": ["sunwell"],
    "nachtbrunnen": ["nightwell"],
    "smaragdgrüner traum": ["emerald dream"],
    "himmelswand": ["skywall"],
    "feuerlande": ["firelands"],
    "schattenlande": ["shadowlands"],
    "eiskrone": ["icecrown"],
    "sturmgipfel": ["storm peaks"],
    "drachenöde": ["dragonblight"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    curated = {json.loads(l)["key"]
               for l in CURATED.read_text(encoding="utf-8").splitlines() if l.strip()}

    hits = []
    total = 0
    for line in TRANS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        total += 1
        if r["key"] in curated:
            continue
        word = r["word"].casefold()
        english = (r.get("translation") or "").casefold()
        for stem, expected in STEMS.items():
            if stem in word and not any(e in english for e in expected):
                r = dict(r)
                r["reasons"] = ["lore-stem"]
                r["stem"] = stem
                r["expected"] = expected[0]
                hits.append(r)
                break

    print(f"przejrzano={total} nieskurowanych z rdzeniem lore i zla angielszczyzna={len(hits)}")
    by_stem = {}
    for r in hits:
        by_stem.setdefault(r["stem"], []).append(r)
    for stem, rows in sorted(by_stem.items(), key=lambda kv: -len(kv[1]))[:12]:
        sample = rows[0]
        print(f'  {stem:<22} {len(rows):>5}  np. {sample["word"]} -> {sample["translation"][:34]}')

    if args.dry_run:
        return 0
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in hits) + "\n",
                   encoding="utf-8")
    print(f"zapisano {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
