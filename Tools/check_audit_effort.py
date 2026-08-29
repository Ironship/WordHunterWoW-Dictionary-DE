#!/usr/bin/env python3
"""Flag batches an agent copied through instead of auditing.

A subagent that returns its input verbatim looks like a clean run to the merge:
every key present, every field valid. Only comparison against the rest of the
wave exposes it. Rerun anything this reports before merging.
"""
import argparse, difflib, json, pathlib, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "Data/cache/audit_work"


def demojibake(text):
    """Undo a UTF-8 string that was written out as if it were Latin-1.

    An agent occasionally emits `jÃ¤hrlichen` for `jährlichen`. The key set then
    diverges from the batch, the word is corrupted the same way so the by-word
    lookup misses too, and the string is far enough from the original that the
    fuzzy match declines it. The byte round-trip is exact, so try it first.
    """
    if "Ã" not in (text or ""):
        return None
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None


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
    # The median only catches a batch that is worse than its wave. When a whole
    # wave slacks off the median drops with it and nothing gets flagged, so keep
    # absolute floors as well. These sit far below a normal wave (which runs
    # 25-40% of translations revised and a note on 70-100% of rows).
    ap.add_argument("--min-change-rate", type=float, default=0.08)
    ap.add_argument("--min-note-rate", type=float, default=0.40)
    args = ap.parse_args()

    stats = []
    for out_path in sorted((WORKDIR / "out").glob("batch_*.jsonl")):
        in_path = WORKDIR / "in" / out_path.name
        if not in_path.exists():
            continue
        src = {r["key"]: r for r in load(in_path)}
        rows = load(out_path)
        # Resolve a key the same way merge_audit does, so this check does not
        # condemn a batch the merge is about to repair. An agent that ASCII-folds
        # the umlauts in a key usually leaves `word` intact, which is enough.
        by_word = {}
        for r in src.values():
            by_word.setdefault(r["word"], []).append(r["key"])

        def resolve(row):
            k = row.get("key")
            if k in src:
                return k
            for cand in (demojibake(k), (k or "").casefold()):
                if cand in src:
                    return cand
            hits = by_word.get(row.get("word"), [])
            if len(hits) == 1:
                return hits[0]
            # Last resort, as in the merge: a near-identical key, never a guess.
            # 0.9 is tight enough that a stray key from another wave will not match.
            near = difflib.get_close_matches(k or "", list(src), n=1, cutoff=0.9)
            return near[0] if near else k
        if not rows:
            stats.append((out_path.name, 0, 0, 0, True, 0)); continue
        # A subagent from an earlier wave can finish after the directory has been
        # rotated and write over the current wave's output. The key sets diverge
        # long before anything else does, so compare them first.
        foreign = {resolve(r) for r in rows} - set(src)
        if foreign:
            print(f"  ! {out_path.name}: {len(foreign)} kluczy spoza tego batcha "
                  f"— mozliwe zanieczyszczenie z innej fali")
        # Structural faults are disqualifying on their own: a dropped or duplicated
        # row is a broken batch no matter how the rest of the wave did.
        broken = []
        if len(rows) != len(src):
            broken.append(f"{len(rows)} wierszy zamiast {len(src)}")
        seen = {}
        for r in rows:
            k = resolve(r)
            seen[k] = seen.get(k, 0) + 1
        dupes = [k for k, c in seen.items() if c > 1]
        if dupes:
            broken.append(f"{len(dupes)} zdublowanych kluczy")
        missing = set(src) - set(seen)
        if missing:
            broken.append(f"{len(missing)} brakujacych kluczy")
        if any(not (r.get("translation") or "").strip() for r in rows):
            broken.append("puste tlumaczenie")
        if broken:
            print(f"  ! {out_path.name}: {', '.join(broken)}")

        changed = sum(1 for r in rows
                      if resolve(r) in src
                      and (r.get("translation") or "").strip() != src[resolve(r)]["current"].strip())
        noted = sum(1 for r in rows if (r.get("note") or "").strip())
        # Advisory only. German capitalises every noun, and the commonest miss on
        # this dictionary is an English gloss that kept the capital. A row left
        # untouched whose gloss is a single capitalised word, and is not simply
        # the name echoed back, is a candidate. Proper nouns land here too, so
        # this is a hint to go and look, never grounds to reject on its own.
        capped = 0
        for r in rows:
            key = resolve(r)
            if key not in src:
                continue
            current = src[key]["current"].strip()
            if (r.get("translation") or "").strip() != current:
                continue
            word = src[key]["word"]
            # A leading capital on the whole gloss is the signal, whether the
            # gloss is one word or several: "Ritual books" for Ritualbuecher is
            # the same miss as "Newt" for Molch. Only the first word is tested,
            # so "Force of Nature" style names are judged on their first word
            # like anything else.
            if (current[:1].isupper()
                    and current.split()[0].casefold() != word.casefold()
                    and current.casefold() != word.casefold()):
                capped += 1
        stats.append((out_path.name, len(rows), changed, noted, bool(broken), capped))

    if not stats:
        print("brak batchy")
        return 0
    med_ch = statistics.median(s[2] / max(s[1], 1) for s in stats)
    med_nt = statistics.median(s[3] / max(s[1], 1) for s in stats)
    suspect = []
    for name, n, ch, nt, broken, capped in stats:
        rate_ch = ch / max(n, 1)
        rate_nt = nt / max(n, 1)
        share_ch = rate_ch / med_ch if med_ch else 1
        share_nt = rate_nt / med_nt if med_nt else 1
        why = []
        if broken:
            why.append("blad struktury")
        if share_ch < args.min_share and share_nt < args.min_share:
            why.append("ponizej mediany fali")
        if rate_ch < args.min_change_rate:
            why.append(f"zmian {rate_ch:.0%}")
        if rate_nt < args.min_note_rate:
            why.append(f"notatek {rate_nt:.0%}")
        if why:
            suspect.append(name)
        print(f"  {name}: {n:>3} wierszy, {ch:>3} zmian, {nt:>3} notatek, {capped:>3} wielkich liter do sprawdzenia"
              + (f"   <-- PODEJRZANY ({', '.join(why)})" if why else ""))
    print(f"\nmediana fali: zmian {med_ch:.0%}, notatek {med_nt:.0%}"
          f" | progi bezwzgledne: zmian {args.min_change_rate:.0%}, notatek {args.min_note_rate:.0%}")
    if suspect:
        print(f"do ponownego przebiegu: {' '.join(suspect)}")
        return 1
    print("wszystkie batche wykonaly realna prace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
