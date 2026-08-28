#!/usr/bin/env python3
"""Flag batches an agent copied through instead of auditing.

A subagent that returns its input verbatim looks like a clean run to the merge:
every key present, every field valid. Only comparison against the rest of the
wave exposes it. Rerun anything this reports before merging.
"""
import argparse, json, pathlib, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "Data/cache/audit_work"


def load(path):
    out, bad = [], 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    if bad:
        print(f"  ! {path.name}: {bad} nieparsowalnych wierszy")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-share", type=float, default=0.25,
                    help="flag a batch below this fraction of the wave's median rate")
    args = ap.parse_args()

    stats = []
    for out_path in sorted((WORKDIR / "out").glob("batch_*.jsonl")):
        in_path = WORKDIR / "in" / out_path.name
        if not in_path.exists():
            continue
        src = {r["key"]: r for r in load(in_path)}
        rows = load(out_path)
        if not rows:
            stats.append((out_path.name, 0, 0, 0)); continue
        # A subagent from an earlier wave can finish after the directory has been
        # rotated and write over the current wave's output. The key sets diverge
        # long before anything else does, so compare them first.
        foreign = {r.get("key") for r in rows} - set(src)
        foreign = {k for k in foreign if (k or "").casefold() not in src}
        if foreign:
            print(f"  ! {out_path.name}: {len(foreign)} kluczy spoza tego batcha "
                  f"— mozliwe zanieczyszczenie z innej fali")
        changed = sum(1 for r in rows
                      if r.get("key") in src
                      and (r.get("translation") or "").strip() != src[r["key"]]["current"].strip())
        noted = sum(1 for r in rows if (r.get("note") or "").strip())
        stats.append((out_path.name, len(rows), changed, noted))

    if not stats:
        print("brak batchy")
        return 0
    med_ch = statistics.median(s[2] / max(s[1], 1) for s in stats)
    med_nt = statistics.median(s[3] / max(s[1], 1) for s in stats)
    suspect = []
    for name, n, ch, nt in stats:
        share_ch = (ch / n) / med_ch if med_ch else 1
        share_nt = (nt / n) / med_nt if med_nt else 1
        if share_ch < args.min_share and share_nt < args.min_share:
            suspect.append(name)
        print(f"  {name}: {n:>3} wierszy, {ch:>3} zmian, {nt:>3} notatek"
              + ("   <-- PODEJRZANY" if name in suspect else ""))
    print(f"\nmediana fali: zmian {med_ch:.0%}, notatek {med_nt:.0%}")
    if suspect:
        print(f"do ponownego przebiegu: {' '.join(suspect)}")
        return 1
    print("wszystkie batche wykonaly realna prace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
