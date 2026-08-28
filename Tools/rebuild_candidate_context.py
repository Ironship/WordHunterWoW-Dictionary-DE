#!/usr/bin/env python3
"""Give every audit candidate a context sentence that actually contains it.

The original candidate file pairs each word with a quest sample that often does
not contain the word at all -- 28% of them -- which strips the auditor of its
best evidence about how the word is used. This walks the quest corpus once and
assigns each key the first sentence it genuinely appears in.
"""
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "Data/cache/audit_candidates.jsonl"
QUESTS = ROOT / "Data/cache/quests_deDE.jsonl"
MAX_CHARS = 260
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip()]
    # casefold() already maps the eszett to ss, matching how keys are built
    wanted = {r["key"] for r in rows}
    found = {}

    for line in QUESTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        quest = json.loads(line)
        for field in ("title", "description", "objectives"):
            text = quest.get(field) or ""
            if not text:
                continue
            for raw in SENTENCE.findall(text):
                sentence = " ".join(raw.split())
                if not sentence:
                    continue
                keys = {t.casefold() for t in TOKEN.findall(sentence)} & wanted
                for key in keys - found.keys():
                    found[key] = sentence[:MAX_CHARS]
        if len(found) == len(wanted):
            break

    improved = kept = 0
    for r in rows:
        best = found.get(r["key"])
        old = (r.get("context") or "").casefold()
        already = r["key"] in old
        if best and not already:
            r["context"] = best
            improved += 1
        else:
            kept += 1

    print(f"kandydatow={len(rows)} poprawionych={improved} zostawionych={kept} "
          f"bez zdania w korpusie={len(wanted)-len(found)}")

    if args.dry_run:
        return 0
    CANDIDATES.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                          encoding="utf-8")
    print("audit_candidates.jsonl zapisany")
    return 0


if __name__ == "__main__":
    sys.exit(main())
