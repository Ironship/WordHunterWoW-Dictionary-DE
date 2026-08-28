#!/usr/bin/env python3
"""Validate Claude subagent audit output and merge it into CuratedDE.jsonl.

Every output row is checked against the batch that produced it. Anything that
fails a check is dropped and reported rather than silently written -- a bad
translation is worse than the Google one it would replace.
"""
import argparse, difflib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "Data/cache/claude_audit"
CURATED = ROOT / "Data/CuratedDE.jsonl"
NOTE_MAX = 200


def load_jsonl(path):
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  ! {path.name}:{n} nieparsowalny JSON: {e}")
    return out


def check(row, src):
    key = row.get("key")
    if key not in src:
        return "klucz spoza batcha"
    # word is authoritative in the source; the agent's copy of it is only ever
    # used to recover a mistyped key, never to overwrite the corpus.
    t = (row.get("translation") or "").strip()
    if not t:
        return "puste translation"
    if "�" in t or "�" in (row.get("note") or ""):
        return "znak zastepczy U+FFFD"
    if len(t) > 120:
        return "translation za dlugie"
    note = row.get("note") or ""
    if len(note) > NOTE_MAX:
        return "note za dlugie"
    if "\n" in note or "\n" in t:
        return "znak nowej linii"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    accepted, rejected, repaired, changed, notes_added = [], [], [], 0, 0
    for out_path in sorted((WORKDIR / "out").glob("batch_*.jsonl")):
        in_path = WORKDIR / "in" / out_path.name
        src = {r["key"]: r for r in load_jsonl(in_path)}
        by_word = {}
        for r in src.values():
            by_word.setdefault(r["word"], []).append(r["key"])
        rows = load_jsonl(out_path)
        if len(rows) != len(src):
            print(f"  ~ {out_path.name}: {len(rows)} wierszy wobec {len(src)} na wejsciu")
        seen = set()
        for row in rows:
            # Agents occasionally "fix" a key back to its umlaut/eszett spelling.
            # The addon casefolds s-sharp to ss, so recover the original key from
            # the word field rather than losing the row.
            if row.get("key") not in src:
                cand = by_word.get(row.get("word"), [])
                if len(cand) == 1:
                    print(f"  ~ {out_path.name}: klucz {row.get('key')!r} -> {cand[0]!r} (odzyskany po word)")
                    row["key"] = cand[0]
                    row["word"] = src[cand[0]]["word"]
                    repaired.append(cand[0])
                else:
                    # A mistyped key usually corrupts the word the same way, so the
                    # lookup above misses it. Fall back to the nearest unused key,
                    # but only for a near-identical string -- never a guess.
                    free = [k for k in src if k not in seen]
                    near = difflib.get_close_matches(row.get("key") or "", free, n=1, cutoff=0.9)
                    if near:
                        print(f"  ~ {out_path.name}: klucz {row.get('key')!r} -> {near[0]!r} (dopasowany przyblizeniem)")
                        row["key"] = near[0]
                        row["word"] = src[near[0]]["word"]
                        repaired.append(near[0])
            err = check(row, src)
            if err:
                rejected.append((out_path.name, row.get("key"), err))
                continue
            if row["key"] in seen:
                rejected.append((out_path.name, row["key"], "duplikat"))
                continue
            seen.add(row["key"])
            if row["translation"].strip() != src[row["key"]]["current"].strip():
                changed += 1
            if (row.get("note") or "").strip():
                notes_added += 1
            accepted.append({"key": row["key"], "word": src[row["key"]]["word"],
                             "translation": row["translation"].strip(),
                             "note": (row.get("note") or "").strip()})

    print(f"przyjete={len(accepted)} odrzucone={len(rejected)} naprawione_klucze={len(repaired)} "
          f"zmienione_tlumaczenia={changed} z_notatka={notes_added}")
    for name, key, err in rejected[:25]:
        print(f"  odrzucone {name} {key}: {err}")
    if len(rejected) > 25:
        print(f"  ... i {len(rejected)-25} wiecej")

    if args.dry_run or not accepted:
        return 0

    existing = load_jsonl(CURATED)
    have = {r["key"] for r in existing}
    fresh = [r for r in accepted if r["key"] not in have]
    with CURATED.open("a", encoding="utf-8") as fh:
        for r in fresh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"dopisane do CuratedDE.jsonl: {len(fresh)} (lacznie {len(existing)+len(fresh)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
