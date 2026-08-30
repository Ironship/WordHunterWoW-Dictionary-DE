#!/usr/bin/env python3
"""German words that appear in Classic Era quest text and are not in the
dictionary yet.

    python Tools/extract_classic_words.py --quests <quests.jsonl>

The input is one JSON object per line carrying the German title and objective
line for a quest. What comes out is a wordlist in exactly the shape
build_wordlist.py produces, so translate_google.py and prepare_audit.py take it
without changes -- only the paths differ, so nothing here can touch the Retail
cache.

Only words the dictionary has never seen are emitted. A word already audited
for Retail keeps its translation and its note; re-running it would risk a
second opinion replacing work that was already checked by hand.
"""
import argparse, collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
# The dictionary's own tokenizer. Hyphens and apostrophes hold a word together
# ("Qiraj-Kriegsinsignie", "Jitters'"), and the key is the casefolded form.
TOKEN = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quests", required=True,
                    help="JSONL with localeTitle/localeObjectives per quest")
    ap.add_argument("--curated", default=str(ROOT / "Data/CuratedDE.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "Data/cache/classic/wordlist_deDE.jsonl"))
    args = ap.parse_args()

    known = set()
    curated = pathlib.Path(args.curated)
    if curated.exists():
        for line in curated.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            key = record.get("key") or record.get("word") or ""
            if key:
                known.add(key.casefold())

    counts = collections.Counter()
    forms = collections.defaultdict(collections.Counter)
    contexts = {}
    quests = 0
    for line in pathlib.Path(args.quests).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        fields = [record.get("localeTitle") or "", record.get("localeObjectives") or ""]
        if not any(f.strip() for f in fields):
            continue
        quests += 1
        for text in fields:
            for word in TOKEN.findall(text):
                if len(word) < 2:
                    continue
                key = word.casefold()
                counts[key] += 1
                forms[key][word] += 1
                # The sentence the word was found in. The audit needs it: a
                # bare word list is where wrong guesses come from.
                contexts.setdefault(key, text[:500])

    fresh = [k for k in sorted(counts) if k not in known]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for key in fresh:
            word = forms[key].most_common(1)[0][0]
            f.write(json.dumps({"key": key, "word": word, "count": counts[key],
                                "context": contexts[key]}, ensure_ascii=False) + "\n")
    print(f"quests={quests} words={len(counts)} already known={len(counts) - len(fresh)} "
          f"new={len(fresh)} -> {out}")


if __name__ == "__main__":
    main()
