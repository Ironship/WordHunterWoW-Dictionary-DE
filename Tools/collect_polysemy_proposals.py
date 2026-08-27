#!/usr/bin/env python3
import json, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUT = ROOT / "Data/cache/polysemy_batches"
MUSE = ROOT / "Data/cache/polysemy_muse"
OUT = ROOT / "Data/cache/polysemy_mimo_batches"


def main():
    proposals, errors = [], []
    for source in sorted(INPUT.glob("batch_*.jsonl")):
        reviewed = MUSE / source.name
        original = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not reviewed.exists():
            errors.append(f"missing {reviewed.name}")
            continue
        output = [json.loads(line) for line in reviewed.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(original) != len(output):
            errors.append(f"count {source.name}: {len(original)} != {len(output)}")
            continue
        for index, (entry, proposal) in enumerate(zip(original, output), 1):
            if entry["key"] != proposal.get("key"):
                errors.append(f"key {source.name}:{index}: {entry['key']!r} != {proposal.get('key')!r}")
            if proposal.get("action") == "fix":
                proposals.append({
                    "key": entry["key"],
                    "word": entry["word"],
                    "count": entry["count"],
                    "context": entry["context"],
                    "current_translation": entry["translation"],
                    "current_note": entry["note"],
                    "muse_translation": proposal.get("translation") or "",
                    "muse_note": proposal.get("note") or "",
                    "muse_confidence": proposal.get("confidence") or "low",
                })
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    batch_size = 50
    for offset in range(0, len(proposals), batch_size):
        path = OUT / f"batch_{offset // batch_size:02d}.jsonl"
        batch = proposals[offset:offset + batch_size]
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in batch) + "\n", encoding="utf-8")
        print(path.name, len(batch))
    print(f"proposals={len(proposals)} validation_errors={len(errors)}")
    for error in errors[:30]: print("ERROR", error)


if __name__ == "__main__": main()
