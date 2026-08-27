#!/usr/bin/env python3
import collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß]+(?:[-'][A-Za-zÄÖÜäöüß]+)*")
counts, forms, contexts = collections.Counter(), collections.defaultdict(collections.Counter), {}
for line in (ROOT / "Data/cache/quests_deDE.jsonl").read_text(encoding="utf-8").splitlines():
    q = json.loads(line)
    for text in (q.get("title") or "", q.get("description") or "", q.get("objectives") or ""):
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
