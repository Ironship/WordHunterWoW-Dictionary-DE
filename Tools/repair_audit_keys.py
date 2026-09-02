#!/usr/bin/env python3
"""Restore the key and word of every audited row from the batch it came from.

The lookup key is casefolded the way the addon looks words up, which means the
eszett is written ss: the key for Fleißaufgabe is fleissaufgabe. A reviewer that
knows German well "corrects" that back to fleißaufgabe, and the entry then
matches nothing the addon ever asks for -- the word silently stops working, with
no error anywhere. The same goes for folding an umlaut to ue, and for
re-capitalising the word.

None of that touches the translation or the note, which is the work worth
keeping. So rather than throw the batch away and pay for it again, this puts the
key and the word back exactly as they were handed out and leaves the rest.

Rows are matched by position, which is safe because a batch whose row count or
order has changed is rejected before this runs.

    python Tools/repair_audit_keys.py            # repair Data/cache/audit_work
    python Tools/repair_audit_keys.py --dry-run
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "Data/cache/audit_work"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(WORKDIR))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    workdir = pathlib.Path(args.workdir)

    total_keys = total_words = repaired_files = 0
    rejected = []
    for out_path in sorted((workdir / "out").glob("*.jsonl")):
        in_path = workdir / "in" / out_path.name
        if not in_path.exists():
            rejected.append(f"{out_path.name}: no matching input")
            continue
        source = [json.loads(line) for line in
                  in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        try:
            audited = [json.loads(line) for line in
                       out_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            rejected.append(f"{out_path.name}: unparsable ({error})")
            continue
        if len(audited) != len(source):
            rejected.append(f"{out_path.name}: {len(audited)} rows against {len(source)}")
            continue
        if any(not (row.get("translation") or "").strip() for row in audited):
            rejected.append(f"{out_path.name}: an empty translation")
            continue

        keys = words = 0
        rows = []
        for original, row in zip(source, audited):
            if row.get("key") != original["key"]:
                keys += 1
            if row.get("word") != original["word"]:
                words += 1
            rows.append({"key": original["key"], "word": original["word"],
                         "translation": row["translation"],
                         "note": row.get("note", "")})
        if keys or words:
            repaired_files += 1
            total_keys += keys
            total_words += words
            print(f"  {out_path.name}: {keys} keys, {words} words restored")
        if not args.dry_run:
            out_path.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                encoding="utf-8")

    print(f"repaired {total_keys} keys and {total_words} words "
          f"across {repaired_files} batches")
    if rejected:
        print("rejected, needs a rerun:")
        for line in rejected:
            print(f"  {line}")
    if args.dry_run:
        print("dry run, nothing written")


if __name__ == "__main__":
    main()
