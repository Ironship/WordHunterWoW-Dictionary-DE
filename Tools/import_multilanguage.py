#!/usr/bin/env python3
"""Read a MultiLanguage language pack for the German words it contains.

Blizzard's Game Data API publishes a quest's title and description and nothing
else. It does not publish the objective line, the text an NPC speaks while the
quest is in progress, or the text spoken when it is handed in. Those three are
a large part of what a player actually reads, and until now the dictionary had
almost none of it: 52 objective lines and 13 progress lines against 28,888
descriptions.

The MultiLanguage addon by Ruben Zantingh carries all three, for far more
quests than the API returns. He gave permission to use it. What this script
takes from it is vocabulary, not text: quest text lands in Data/cache, which is
not part of the repository and is never packaged, and what ships is a list of
single words with translations and notes written for this project.

Existing entries win. A field the API already filled is never overwritten, so
Blizzard's own wording stays authoritative wherever it exists.

    python Tools/import_multilanguage.py path/to/MultiLanguage_DE/Database/Quests/quests.lua
"""
import argparse, html, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "Data/cache/quests_deDE.jsonl"

ROW = re.compile(r"MultiLanguageQuestData\[[^\]]+\]\[(\d+)\] = \{(.*)\}\s*$")
FIELD = re.compile(r"(\w+) = (nil|\"(?:\\.|[^\"\\])*\")")

# rewards is a run-together list of item names with no sentence structure, and
# the reward line repeats verbatim on tens of thousands of quests. Nothing in it
# teaches a word in context, so it is not read.
WANTED = {"title": "title", "objective": "objectives", "description": "description",
          "progress": "progress", "completion": "completion"}

# The scrape kept HTML escapes for the angle brackets Blizzard uses around
# substitutions, so <name> arrives as &lt;name&gt; and tokenises as "lt" + "gt".
# Those two were the most frequent "new words" in the file before this.
def clean(text):
    text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    text = html.unescape(text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="quests.lua from a MultiLanguage language pack")
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cache = pathlib.Path(args.cache)
    quests = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                q = json.loads(line)
                quests[q["id"]] = q
    before = len(quests)

    added, filled = 0, {k: 0 for k in WANTED.values()}
    for line in pathlib.Path(args.source).read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        qid = int(m.group(1))
        row = {}
        for key, raw in FIELD.findall(m.group(2)):
            if key in WANTED and raw != "nil":
                value = clean(raw[1:-1])
                if value:
                    row[WANTED[key]] = value
        if not row:
            continue
        q = quests.get(qid)
        if q is None:
            q = {"id": qid}
            quests[qid] = q
            added += 1
        for field, value in row.items():
            if not (q.get(field) or "").strip():
                q[field] = value
                filled[field] += 1

    print(f"quests before={before} after={len(quests)} new={added}")
    for field, n in filled.items():
        print(f"  filled {field}: {n}")
    if args.dry_run:
        print("dry run, nothing written")
        return
    with cache.open("w", encoding="utf-8") as f:
        for qid in sorted(quests):
            f.write(json.dumps(quests[qid], ensure_ascii=False) + "\n")
    print(f"wrote {cache}")


if __name__ == "__main__":
    main()
