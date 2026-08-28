#!/usr/bin/env python3
"""Prepare a notes-only pass over already-curated entries.

Translations in CuratedDE.jsonl are hand-checked and must survive untouched;
only the note field is up for rewriting, so that older entries read in the same
voice as newly audited ones.
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CURATED = ROOT / "Data/CuratedDE.jsonl"
TRANS = ROOT / "Data/cache/translations_de_en.jsonl"
WORKDIR = ROOT / "Data/cache/notes_work"
CONTEXT_CHARS = 220


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--batch-size", type=int, default=60)
    args = ap.parse_args()

    rows = [json.loads(l) for l in CURATED.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[:args.limit]

    ctx = {}
    for line in TRANS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["key"] in {x["key"] for x in rows}:
            ctx[r["key"]] = r.get("context", "")

    indir = WORKDIR / "in"
    indir.mkdir(parents=True, exist_ok=True)
    (WORKDIR / "out").mkdir(parents=True, exist_ok=True)
    for p in indir.glob("*.jsonl"):
        p.unlink()

    n = 0
    for i in range(0, len(rows), args.batch_size):
        chunk = rows[i:i + args.batch_size]
        slim = [{"key": r["key"], "word": r["word"], "translation": r["translation"],
                 "note": r.get("note", ""),
                 "context": " ".join(ctx.get(r["key"], "").split())[:CONTEXT_CHARS]}
                for r in chunk]
        (indir / f"batch_{n:02d}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in slim) + "\n", encoding="utf-8")
        n += 1
    print(f"entries={len(rows)} batches={n}")


if __name__ == "__main__":
    main()
