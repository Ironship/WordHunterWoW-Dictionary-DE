#!/usr/bin/env python3
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
def q(value): return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n') + '"'
records = {}
for source in (ROOT / "Data/cache/translations_de_en.jsonl", ROOT / "Data/CuratedDE.jsonl"):
    for line in source.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("translation"): records[r["key"]] = r
lines = ["WordHunterWoW_Dictionary_DE = WordHunterWoW_Dictionary_DE or {}"]
for key in sorted(records):
    r = records[key]
    extras = ""
    if r.get("status") in ("ignored", "known", "learning", "new"):
        extras = f", status = {q(r['status'])}"
    lines.append(f"WordHunterWoW_Dictionary_DE[{q(key)}] = {{ word = {q(r['word'])}, translation = {q(r['translation'])}, note = {q(r.get('note'))}{extras} }}")
(ROOT / "Data/DictionaryDE.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"entries={len(records)}")
