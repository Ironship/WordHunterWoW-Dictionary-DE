#!/usr/bin/env python3
"""Split the Classic Era words into per-agent audit batches.

    python Tools/prepare_classic_audit.py --limit 4200 --batch-size 150

Same shape as prepare_audit.py, and deliberately a separate file: it reads the
Classic caches and writes to a Classic work directory, so a run here can never
add to, overwrite, or re-audit anything on the Retail side.

A word already in CuratedDE.jsonl is skipped. It was checked by hand once and a
second opinion would only risk replacing that work with a worse one.
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORDLIST = ROOT / "Data/cache/classic/wordlist_deDE.jsonl"
TRANSLATIONS = ROOT / "Data/cache/classic/translations_de_en.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
WORKDIR = ROOT / "Data/cache/classic/audit_work"
CONTEXT_CHARS = 300


def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=4200)
    ap.add_argument("--batch-size", type=int, default=150)
    ap.add_argument("--offset", type=int, default=0)
    args = ap.parse_args()

    done = {r["key"] for r in load_jsonl(CURATED) if r.get("key")}
    outdir = WORKDIR / "out"
    if outdir.exists():
        for path in sorted(outdir.glob("*.jsonl")):
            done.update(r["key"] for r in load_jsonl(path) if r.get("key"))

    context = {r["key"]: r.get("context", "") for r in load_jsonl(WORDLIST)}
    counts = {r["key"]: r.get("count", 0) for r in load_jsonl(WORDLIST)}

    rows = [r for r in load_jsonl(TRANSLATIONS) if r.get("key") and r["key"] not in done]
    # Commonest first, so a wave that gets cut short has still covered the words
    # a player actually meets.
    rows.sort(key=lambda r: -counts.get(r["key"], 0))
    rows = rows[args.offset:args.offset + args.limit]

    indir = WORKDIR / "in"
    indir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in indir.glob("batch_*.jsonl"):
        old.unlink()

    batches = 0
    for i in range(0, len(rows), args.batch_size):
        chunk = rows[i:i + args.batch_size]
        slim = [{"key": r["key"], "word": r["word"], "current": r.get("translation", ""),
                 "count": counts.get(r["key"], 0),
                 "context": " ".join(context.get(r["key"], "").split())[:CONTEXT_CHARS]}
                for r in chunk]
        path = indir / f"batch_{batches:02d}.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in slim) + "\n",
                        encoding="utf-8")
        batches += 1
    print(f"selected={len(rows)} batches={batches} already_done={len(done)}")


if __name__ == "__main__":
    main()
