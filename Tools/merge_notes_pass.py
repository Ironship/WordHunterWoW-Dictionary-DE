#!/usr/bin/env python3
"""Merge the notes-only pass back into CuratedDE.jsonl.

Only the note field may move. If an agent touched key, word or translation the
row is refused outright -- those were hand-checked and are not up for revision.
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "Data/cache/notes_work"
CURATED = ROOT / "Data/CuratedDE.jsonl"
NOTE_MAX = 200
NEWLINE = chr(10)
BAD = chr(0xFFFD)


def load_jsonl(path):
    out = []
    if not path.exists():
        return out
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  ! {path.name}:{n} nieparsowalny JSON: {e}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    updates, rejected, changed = {}, [], 0
    for out_path in sorted((WORKDIR / "out").glob("batch_*.jsonl")):
        src = {r["key"]: r for r in load_jsonl(WORKDIR / "in" / out_path.name)}
        for row in load_jsonl(out_path):
            key = row.get("key")
            base = src.get(key)
            if base is None:
                rejected.append((out_path.name, key, "klucz spoza batcha")); continue
            if row.get("word") != base["word"]:
                rejected.append((out_path.name, key, "zmienione word")); continue
            if (row.get("translation") or "").strip() != base["translation"].strip():
                rejected.append((out_path.name, key,
                                 f'zmienione translation: {base["translation"]!r} -> {row.get("translation")!r}'))
                continue
            note = (row.get("note") or "").strip()
            if len(note) > NOTE_MAX or NEWLINE in note or BAD in note:
                rejected.append((out_path.name, key, "notatka niepoprawna")); continue
            if note != (base.get("note") or "").strip():
                changed += 1
            updates[key] = note

    print(f"wierszy={len(updates)} odrzucone={len(rejected)} zmienione_notatki={changed}")
    for name, key, err in rejected[:20]:
        print(f"  odrzucone {name} {key}: {err}")
    if len(rejected) > 20:
        print(f"  ... i {len(rejected)-20} wiecej")

    if args.dry_run or not updates:
        return 0

    rows = load_jsonl(CURATED)
    applied = 0
    for r in rows:
        if r["key"] in updates and (r.get("note") or "").strip() != updates[r["key"]]:
            r["note"] = updates[r["key"]]
            applied += 1
    CURATED.write_text(NEWLINE.join(json.dumps(r, ensure_ascii=False) for r in rows) + NEWLINE,
                       encoding="utf-8")
    print(f"zaktualizowane notatki w CuratedDE.jsonl: {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
