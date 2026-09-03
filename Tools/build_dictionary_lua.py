#!/usr/bin/env python3
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def q(value):
    return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"') \
        .replace('\r', '').replace('\n', '\\n') + '"'


parser = argparse.ArgumentParser()
parser.add_argument("--all", action="store_true",
                    help="ship every cached word, including ones no longer in "
                         "the corpus")
args = parser.parse_args()

# Only words the corpus still contains are shipped. The translation cache keeps
# everything ever looked up, including the English words that came from
# untranslated quest rows before build_wordlist.py learned to skip them, and a
# German dictionary has no business holding an entry that reads
# the -> the.
live = None
wordlist = ROOT / "Data/cache/wordlist_deDE.jsonl"
if wordlist.exists() and not args.all:
    live = {json.loads(line)["key"]
            for line in wordlist.read_text(encoding="utf-8").splitlines()
            if line.strip()}

records = {}
for source in (ROOT / "Data/cache/translations_de_en.jsonl",
               ROOT / "Data/CuratedDE.jsonl"):
    for line in source.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if live is not None and r.get("key") not in live:
            continue
        if r.get("translation"):
            records[r["key"]] = r

lines = ["WordHunterWoW_Dictionary_DE = WordHunterWoW_Dictionary_DE or {}"]
for key in sorted(records):
    r = records[key]
    extras = ""
    if r.get("status") in ("ignored", "known", "learning", "new"):
        extras = f", status = {q(r['status'])}"
    lines.append(f"WordHunterWoW_Dictionary_DE[{q(key)}] = {{ word = {q(r['word'])}, "
                 f"translation = {q(r['translation'])}, note = {q(r.get('note'))}{extras} }}")
(ROOT / "Data/DictionaryDE.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"entries={len(records)}")
