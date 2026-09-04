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

# An entry is dropped only when it is both absent from the corpus and reads
# English-to-English -- the -> the, default -> Default. Those came from quest
# rows that were never translated, which build_wordlist.py now skips, and a
# German dictionary has no business holding them.
#
# Absence from the corpus is not on its own a reason to drop anything. The
# curated file holds inflections that a fuller corpus once carried --
# monatlicher, monatliches -- and a player who meets one of those in text this
# corpus happens not to include should still be able to look it up.
live = None
wordlist = ROOT / "Data/cache/wordlist_deDE.jsonl"
if wordlist.exists() and not args.all:
    live = {json.loads(line)["key"]
            for line in wordlist.read_text(encoding="utf-8").splitlines()
            if line.strip()}


def english_leftover(record):
    if live is None or record.get("key") in live:
        return False
    return (record.get("translation") or "").strip().casefold() == \
        (record.get("word") or "").strip().casefold()


records = {}
for source in (ROOT / "Data/cache/translations_de_en.jsonl",
               ROOT / "Data/CuratedDE.jsonl"):
    for line in source.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if english_leftover(r):
            continue
        if r.get("translation"):
            records[r["key"]] = r

# WoW's Lua 5.1 stores every string in a per-function constant table capped
# at 2^18-1 (262143). One assignment is up to four unique strings (key, word,
# translation, note), so ~100k entries overflow and the client reports
# "constant table overflow" at line 1. Nested functions each get their own table.
ENTRIES_PER_FUNCTION = 20000

keys = sorted(records)
lines = ["WordHunterWoW_Dictionary_DE = WordHunterWoW_Dictionary_DE or {}"]
for i in range(0, len(keys), ENTRIES_PER_FUNCTION):
    lines.append(";(function()")
    for key in keys[i:i + ENTRIES_PER_FUNCTION]:
        r = records[key]
        extras = ""
        if r.get("status") in ("ignored", "known", "learning", "new"):
            extras = f", status = {q(r['status'])}"
        lines.append(f"WordHunterWoW_Dictionary_DE[{q(key)}] = {{ word = {q(r['word'])}, "
                     f"translation = {q(r['translation'])}, note = {q(r.get('note'))}{extras} }}")
    lines.append("end)()")
(ROOT / "Data/DictionaryDE.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"entries={len(records)} chunks={(len(keys) + ENTRIES_PER_FUNCTION - 1) // ENTRIES_PER_FUNCTION}")
