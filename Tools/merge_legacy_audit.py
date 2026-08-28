#!/usr/bin/env python3
"""Fold the previous session's audit_output.jsonl into CuratedDE.jsonl.

That file was produced by a hand-curated pass but never applied. It carries no
word field -- recovered here from the translation corpus -- and it carries a
status field, which the Lua builder uses to mark proper names as ignored.
Entries already curated keep their current translation and note; only the
status is adopted, since nothing else in the newer pass records it.
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEGACY = ROOT / "audit_output.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
TRANS = ROOT / "Data/cache/translations_de_en.jsonl"
NEWLINE = chr(10)
KNOWN_STATUS = {"ignored", "known", "learning", "new"}


def load(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    legacy = load(LEGACY)
    words = {}
    for line in TRANS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        words[r["key"]] = r["word"]

    rows = load(CURATED)
    by_key = {r["key"]: r for r in rows}

    added, status_only, skipped = [], 0, []
    for r in legacy:
        key = r["key"]
        word = words.get(key)
        if word is None:
            skipped.append((key, "brak slowa w korpusie")); continue
        status = r.get("status") if r.get("status") in KNOWN_STATUS else None
        if key in by_key:
            if status and by_key[key].get("status") != status:
                by_key[key]["status"] = status
                status_only += 1
            continue
        translation = (r.get("translation") or "").strip()
        if not translation:
            skipped.append((key, "puste tlumaczenie")); continue
        entry = {"key": key, "word": word, "translation": translation,
                 "note": (r.get("note") or "").strip()}
        if status:
            entry["status"] = status
        added.append(entry)

    print(f"legacy={len(legacy)} nowych={len(added)} status_dodany_do_istniejacych={status_only} "
          f"pominietych={len(skipped)}")
    for key, why in skipped[:10]:
        print(f"  pominieto {key}: {why}")

    if args.dry_run:
        return 0

    rows.extend(added)
    CURATED.write_text(NEWLINE.join(json.dumps(r, ensure_ascii=False) for r in rows) + NEWLINE,
                       encoding="utf-8")
    print(f"CuratedDE.jsonl: {len(rows)} wpisow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
