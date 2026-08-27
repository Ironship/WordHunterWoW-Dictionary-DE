#!/usr/bin/env python3
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "Data/cache/audit_candidates.jsonl"
OUT = ROOT / "Data/cache/audit_batches"
OUT.mkdir(parents=True, exist_ok=True)

PRIORITY = {"empty", "garbage", "untranslated", "overtranslated", "literal-blob"}
rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
must = [r for r in rows if PRIORITY.intersection(r["reasons"])]
rest = [r for r in rows if r not in must]
rest.sort(key=lambda r: (-int(r["count"] or 0), -len(r["word"])))
selected = must + rest[:500]
print(f"must={len(must)} extra={min(500,len(rest))} total={len(selected)}")

size = 90
for i in range(0, len(selected), size):
    chunk = selected[i:i + size]
    path = OUT / f"batch_{i // size:02d}.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in chunk) + "\n", encoding="utf-8")
    print(path.name, len(chunk))
