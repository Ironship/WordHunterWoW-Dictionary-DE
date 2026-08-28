#!/usr/bin/env python3
"""Prepare audit batches for Claude subagents.

Selects compound (Komposita) candidates -- where machine translation is weakest
and where an explanatory note carries the most value -- skips anything already
curated by hand, and splits the result into per-agent batch files.
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "Data/cache/audit_candidates.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
WORKDIR = ROOT / "Data/cache/claude_audit"
CONTEXT_CHARS = 220


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", default="compound",
                    help="candidate reason to select, or 'any' for every remaining candidate")
    ap.add_argument("--limit", type=int, default=720, help="how many entries this wave")
    ap.add_argument("--batch-size", type=int, default=60)
    ap.add_argument("--offset", type=int, default=0, help="skip N entries (for later waves)")
    args = ap.parse_args()

    done = {r["key"] for r in load_jsonl(CURATED)}
    for path in sorted((WORKDIR / "out").glob("*.jsonl")) if (WORKDIR / "out").exists() else []:
        done.update(r["key"] for r in load_jsonl(path))

    rows = [r for r in load_jsonl(CANDIDATES)
            if (args.reason == "any" or args.reason in r.get("reasons", []))
            and r["key"] not in done]
    rows.sort(key=lambda r: -r.get("count", 0))
    rows = rows[args.offset:args.offset + args.limit]

    indir = WORKDIR / "in"
    indir.mkdir(parents=True, exist_ok=True)
    (WORKDIR / "out").mkdir(parents=True, exist_ok=True)

    batches = 0
    for i in range(0, len(rows), args.batch_size):
        chunk = rows[i:i + args.batch_size]
        slim = [{"key": r["key"], "word": r["word"], "current": r["translation"],
                 "count": r.get("count", 0),
                 "context": " ".join(r.get("context", "").split())[:CONTEXT_CHARS]}
                for r in chunk]
        out = indir / f"batch_{batches:02d}.jsonl"
        out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in slim) + "\n", encoding="utf-8")
        batches += 1
    print(f"selected={len(rows)} batches={batches} skipped_already_done={len(done)}")


if __name__ == "__main__":
    main()
