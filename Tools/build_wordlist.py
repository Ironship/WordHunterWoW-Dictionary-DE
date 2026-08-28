#!/usr/bin/env python3
import collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)
counts, forms, contexts = collections.Counter(), collections.defaultdict(collections.Counter), {}
for line in (ROOT / "Data/cache/quests_deDE.jsonl").read_text(encoding="utf-8").splitlines():
    q = json.loads(line)
    # progress and reward only ever arrive via import_harvest.py -- the quest API
    # publishes neither, and objectives comes back empty from it too.
    for field in ("title", "description", "objectives", "progress", "reward"):
        text = q.get(field) or ""
        for word in TOKEN.findall(text):
            if len(word) < 2: continue
            key = word.casefold(); counts[key] += 1; forms[key][word] += 1
            contexts.setdefault(key, text[:500])
out = ROOT / "Data/cache/wordlist_deDE.jsonl"
with out.open("w", encoding="utf-8") as f:
    for key in sorted(counts):
        word = forms[key].most_common(1)[0][0]
        f.write(json.dumps({"key": key, "word": word, "count": counts[key], "context": contexts[key]}, ensure_ascii=False) + "\n")
print(f"words={len(counts)} output={out}")
