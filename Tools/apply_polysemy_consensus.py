#!/usr/bin/env python3
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUT = ROOT / "Data/cache/polysemy_mimo_batches"
REVIEW = ROOT / "Data/cache/polysemy_mimo"
CURATED = ROOT / "Data/CuratedDE.jsonl"
PREVIEW = ROOT / "Data/cache/polysemy_consensus.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    accepted, rejected, errors = [], 0, []
    for source in sorted(INPUT.glob("batch_*.jsonl")):
        review_path = REVIEW / source.name
        original = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not review_path.exists():
            errors.append(f"missing {review_path.name}")
            continue
        reviews = [json.loads(line) for line in review_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(original) != len(reviews):
            errors.append(f"count {source.name}: {len(original)} != {len(reviews)}")
            continue
        for index, (entry, review) in enumerate(zip(original, reviews), 1):
            if entry["key"] != review.get("key"):
                errors.append(f"key {source.name}:{index}: {entry['key']!r} != {review.get('key')!r}")
                continue
            if "�" in json.dumps(review, ensure_ascii=False):
                errors.append(f"encoding {source.name}:{index}: {entry['key']}")
                continue
            if review.get("action") == "reject" or review.get("confidence") != "high":
                rejected += 1
                continue
            translation = (review.get("translation") or "").strip()
            note = (review.get("note") or "").strip()
            if not translation or len(note) > 100:
                errors.append(f"invalid final {source.name}:{index}: {entry['key']}")
                continue
            accepted.append({"key": entry["key"], "word": entry["word"], "translation": translation, "note": note})
    PREVIEW.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in accepted) + ("\n" if accepted else ""), encoding="utf-8")
    print(f"accepted_high={len(accepted)} rejected_or_nonhigh={rejected} errors={len(errors)} preview={PREVIEW}")
    for error in errors[:30]: print("ERROR", error)
    if errors or not args.apply:
        return 1 if errors else 0

    curated = {}
    order = []
    for line in CURATED.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        item = json.loads(line)
        curated[item["key"]] = item
        order.append(item["key"])
    added = 0
    for item in accepted:
        if item["key"] not in curated:
            order.append(item["key"])
            added += 1
        curated[item["key"]] = item
    CURATED.write_text("\n".join(json.dumps(curated[key], ensure_ascii=False, separators=(",", ":")) for key in order) + "\n", encoding="utf-8")
    print(f"curated_total={len(curated)} added={added} updated={len(accepted) - added}")


if __name__ == "__main__":
    raise SystemExit(main())
