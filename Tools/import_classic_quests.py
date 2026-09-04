#!/usr/bin/env python3
"""Add the Classic Era quest text to the pack's one quest corpus.

    python Tools/import_classic_quests.py --quests <classic.jsonl> --locale deDE

The input is one JSON object per line with localeTitle and localeObjectives,
as Tools/extract_classic_quests.lua in the English panel writes it from the
Questie database. The offer text -- the paragraph an NPC speaks -- is not in
that source and is not invented here.

There is one corpus, not two. A Classic quest and a Retail quest can share a
numeric id and be different quests, so Classic rows are keyed "classic-<id>"
and sit beside the Retail ones. Nothing is removed from either side: the
dictionary is keyed by the word, and a word is the same word on both games. The
same import run twice adds nothing.
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quests", required=True,
                    help="JSONL with localeTitle/localeObjectives per quest")
    ap.add_argument("--locale", required=True, help="e.g. deDE, esES, ptBR")
    args = ap.parse_args()

    corpus = ROOT / f"Data/cache/quests_{args.locale}.jsonl"
    present = set()
    if corpus.exists():
        for line in corpus.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    present.add(str(json.loads(line).get("id")))
                except Exception:
                    pass

    added = skipped = empty = 0
    with corpus.open("a", encoding="utf-8") as out:
        for line in pathlib.Path(args.quests).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            title = (record.get("localeTitle") or "").strip()
            objectives = (record.get("localeObjectives") or "").strip()
            if not title and not objectives:
                empty += 1
                continue
            ident = f"classic-{record.get('id')}"
            if ident in present:
                skipped += 1
                continue
            out.write(json.dumps({"id": ident, "title": title, "objectives": objectives,
                                  "description": "", "game": "classic"},
                                 ensure_ascii=False) + "\n")
            present.add(ident)
            added += 1
    print(f"locale={args.locale} added={added} already_present={skipped} "
          f"untranslated={empty} corpus={corpus}")


if __name__ == "__main__":
    main()
