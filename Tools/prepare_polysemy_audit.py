#!/usr/bin/env python3
import argparse, json, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "Data/cache/translations_de_en.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
OUT = ROOT / "Data/cache/polysemy_batches"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=960)
    parser.add_argument("--batch-size", type=int, default=60)
    args = parser.parse_args()
    curated = {json.loads(line)["key"] for line in CURATED.read_text(encoding="utf-8").splitlines() if line.strip()}
    records = []
    for line in TRANSLATIONS.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["key"] in curated or not record.get("translation"): continue
        records.append({
            "key": record["key"],
            "word": record["word"],
            "translation": record["translation"],
            "note": record.get("note") or "",
            "count": record.get("count") or 0,
            "context": (record.get("context") or "")[:320],
        })
    records.sort(key=lambda record: (-int(record["count"]), record["key"]))
    records = records[:args.limit]
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for offset in range(0, len(records), args.batch_size):
        batch = records[offset:offset + args.batch_size]
        path = OUT / f"batch_{offset // args.batch_size:02d}.jsonl"
        path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in batch) + "\n", encoding="utf-8")
        print(path.name, len(batch))
    print(f"total={len(records)} batches={(len(records) + args.batch_size - 1) // args.batch_size}")


if __name__ == "__main__": main()
