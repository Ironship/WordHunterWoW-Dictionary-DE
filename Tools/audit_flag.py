#!/usr/bin/env python3
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "Data/cache/translations_de_en.jsonl"
OUT = ROOT / "Data/cache/audit_candidates.jsonl"

FUNCTION_WORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "einen",
    "und", "oder", "aber", "als", "auch", "noch", "nur", "schon", "sehr", "viel",
    "von", "vom", "zu", "zum", "zur", "in", "im", "an", "am", "auf", "aus", "bei",
    "mit", "nach", "vor", "für", "über", "unter", "durch", "gegen", "ohne", "um",
    "ist", "sind", "war", "wird", "werden", "hat", "haben", "sein", "ich", "ihr",
    "wir", "sie", "es", "er", "du", "euch", "uns", "mir", "dir", "sich",
}

COMPOUND_MARKERS = (
    "meister", "wächter", "krieger", "jäger", "stein", "feuer", "wasser", "blut",
    "schatten", "licht", "dunkel", "nacht", "sturm", "wind", "berg", "wald",
    "dorf", "stadt", "burg", "turm", "festung", "tempel", "höhle", "mine",
    "klinge", "axt", "hammer", "schild", "rüstung", "helm", "stiefel",
    "käfig", "kerker", "gefängnis", "zuflucht", "lager", "hügel", "tal",
    "bruder", "schwester", "mutter", "vater", "kind", "volk", "stamm",
    "magier", "priester", "schamane", "druide", "hexen", "dämon", "untot",
    "drachen", "wyrm", "bestie", "wild", "tier", "bär", "wolf", "adler",
    "silber", "gold", "eisen", "stahl", "holz", "leder", "seide",
    "quest", "auftrag", "mission", "belohnung", "erfahrung",
)

UMLAUT = re.compile(r"[äöüÄÖÜß]")
LETTERS = re.compile(r"[A-Za-zÄÖÜäöüß]")


def looks_german(word: str) -> bool:
    if UMLAUT.search(word):
        return True
    low = word.lower()
    return any(low.endswith(s) for s in ("ung", "heit", "keit", "schaft", "lich", "isch", "chen", "lein", "heit"))


def flag(rec: dict) -> list[str]:
    word = rec.get("word") or ""
    key = rec.get("key") or ""
    tr = (rec.get("translation") or "").strip()
    reasons = []
    if not tr:
        reasons.append("empty")
        return reasons
    low_w = word.lower()
    low_t = tr.lower()
    if low_w in FUNCTION_WORDS:
        return reasons
    if not LETTERS.search(word):
        return reasons
    if low_t == low_w and looks_german(word) and len(word) >= 6:
        reasons.append("untranslated")
    if len(word) >= 14:
        reasons.append("long")
    compact = re.sub(r"[^A-Za-zÄÖÜäöüß]", "", word)
    if len(compact) >= 10 and any(m in compact.lower() for m in COMPOUND_MARKERS):
        reasons.append("compound")
    if " " not in tr and len(word) >= 12 and looks_german(word) and low_t == low_w:
        reasons.append("literal-blob")
    if tr.count(" ") >= 4 and len(word) <= 16:
        reasons.append("overtranslated")
    if re.search(r"\b(the the|of of|to to)\b", low_t):
        reasons.append("garbage")
    return reasons


def main():
    n = 0
    flagged = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        n += 1
        reasons = flag(rec)
        if not reasons:
            continue
        flagged.append({
            "key": rec["key"],
            "word": rec["word"],
            "translation": rec.get("translation") or "",
            "note": rec.get("note") or "",
            "count": rec.get("count") or 0,
            "context": (rec.get("context") or "")[:280],
            "reasons": reasons,
        })
    flagged.sort(key=lambda r: (-int(r["count"] or 0), -len(r["word"])))
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in flagged) + ("\n" if flagged else ""), encoding="utf-8")
    by = {}
    for r in flagged:
        for reason in r["reasons"]:
            by[reason] = by.get(reason, 0) + 1
    print(f"scanned={n} flagged={len(flagged)} out={OUT}")
    print("reasons", by)


if __name__ == "__main__":
    sys.exit(main() or 0)
