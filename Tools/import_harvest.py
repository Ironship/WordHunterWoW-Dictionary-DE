#!/usr/bin/env python3
"""Fold text collected in-game back into the quest corpus.

Blizzard's quest API publishes a quest's title and its offer text and nothing
else. There is no objectives field -- it comes back empty for all 30815 quests
in every locale -- and no progress or hand-in text either. NPC gossip is not in
the API at all. So a word that lives only in one of those passages never reaches
the corpus, and therefore never reaches the dictionary: "Besichtigt" is absent
from the German corpus even though "besichtigen" and "Besichtigung" are both in
it, because the imperative only ever appears on an objective line.

The game client has all of it. With text collection switched on
(/whw harvest on) the addon records passages the player actually meets, and
/whw harvest export writes them to SavedVariables as one percent-encoded blob.
This reads that blob and merges it into the corpus.

    python Tools/import_harvest.py --saved "<WoW>/_retail_/WTF/Account/<ACCT>/SavedVariables/WordHunterWoW.lua"

Then rebuild as usual: build_wordlist.py -> translate_google.py -> audit.
"""
import argparse, json, pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLOB = re.compile(r'WordHunterWoWCorpusExport\s*=\s*"((?:[^"\\]|\\.)*)"', re.S)
# Quest passages the addon can see. "gossip" has no quest to attach to and is
# kept as its own record.
QUEST_FIELDS = ("title", "description", "objectives", "progress", "reward")
# "word" and "gossip" are not quest fields and are handled separately.


def read_blob(saved_path):
    text = pathlib.Path(saved_path).read_text(encoding="utf-8", errors="replace")
    match = BLOB.search(text)
    if not match:
        sys.exit(f"no WordHunterWoWCorpusExport in {saved_path}\n"
                 "Run /whw harvest export in game, then log out or /reload so the "
                 "file is written.")
    # The value is a Lua string literal; only the escapes Lua itself emits matter.
    raw = match.group(1).replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
    if not raw.startswith("WHC1|"):
        sys.exit(f"unexpected export format: {raw[:32]!r}")
    _, locale, rows = raw.split("|", 2)
    entries = []
    for row in rows.split(";"):
        if not row:
            continue
        parts = row.split("|")
        if len(parts) != 3:
            print(f"  ! skipping malformed row: {row[:60]!r}")
            continue
        kind, quest_id, encoded = parts
        entries.append((kind, int(quest_id or 0), urllib.parse.unquote(encoded)))
    return locale, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saved", required=True, help="path to SavedVariables/WordHunterWoW.lua")
    ap.add_argument("--locale", help="override the locale recorded in the export")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    locale, entries = read_blob(args.saved)
    if args.locale:
        locale = args.locale
    print(f"export: locale={locale} passages={len(entries)}")

    corpus_path = ROOT / f"Data/cache/quests_{locale}.jsonl"
    if not corpus_path.exists():
        sys.exit(f"no corpus at {corpus_path}")
    quests = {}
    order = []
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        quests[record["id"]] = record
        order.append(record["id"])

    filled, conflicting, new_quests, gossip, unknown = 0, 0, 0, [], []
    for kind, quest_id, text in entries:
        if kind == "word":
            unknown.append(text)
            continue
        if kind == "gossip":
            gossip.append(text)
            continue
        if kind not in QUEST_FIELDS:
            continue
        record = quests.get(quest_id)
        if record is None:
            record = {"id": quest_id, "title": "", "description": "", "objectives": ""}
            quests[quest_id] = record
            order.append(quest_id)
            new_quests += 1
        existing = (record.get(kind) or "").strip()
        if not existing:
            record[kind] = text
            filled += 1
        elif existing != text.strip():
            # The API text and the client text disagree. Keep the API's -- it is
            # what the rest of the corpus was built from -- and say so.
            conflicting += 1

    # Gossip belongs to no quest. Give it its own records with negative ids so it
    # can never collide with a real quest id.
    seen_gossip = {q["description"] for q in quests.values() if q["id"] < 0}
    added_gossip = 0
    next_id = min([q for q in quests if q < 0], default=0) - 1
    for text in gossip:
        if text in seen_gossip:
            continue
        quests[next_id] = {"id": next_id, "title": "", "description": text, "objectives": ""}
        order.append(next_id)
        seen_gossip.add(text)
        next_id -= 1
        added_gossip += 1

    # Words the addon could not gloss are not corpus text -- they are a worklist.
    # Write them where translate_google.py can pick them up rather than folding
    # them into the quests file.
    if unknown:
        seen = set()
        fresh = [w for w in unknown if not (w.casefold() in seen or seen.add(w.casefold()))]
        words_path = ROOT / f"Data/cache/unknown_words_{locale}.txt"
        had = set()
        if words_path.exists():
            had = {l.strip() for l in words_path.read_text(encoding="utf-8").splitlines() if l.strip()}
        added = [w for w in fresh if w not in had]
        with words_path.open("a", encoding="utf-8") as fh:
            for w in added:
                fh.write(w + chr(10))
        print(f"  words with no dictionary entry: {len(fresh)} collected, {len(added)} new -> {words_path.name}")

    print(f"  filled empty fields: {filled}")
    print(f"  disagreed with existing text (kept the corpus): {conflicting}")
    print(f"  quests not previously in the corpus: {new_quests}")
    print(f"  gossip passages added: {added_gossip}")

    if args.dry_run:
        print("dry run, nothing written")
        return 0

    with corpus_path.open("w", encoding="utf-8") as fh:
        for quest_id in order:
            fh.write(json.dumps(quests[quest_id], ensure_ascii=False) + "\n")
    print(f"wrote {len(order)} records to {corpus_path}")
    print("next: build_wordlist.py -> translate_google.py -> audit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
