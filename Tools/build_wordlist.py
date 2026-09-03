#!/usr/bin/env python3
import argparse, collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)

# The English text of the same quests. A field that is the English one rather
# than the German is an untranslated row sitting in the locale file, and its
# words are not German words. Left in, they crowd the top of the uncurated list:
# on the Italian pack an audit wave came back 90% English function words,
# because every real word above them had already been done.
ENGLISH = ROOT.parent / "WordHunterWoW-ENPanel/Data/cache/quests_enUS.jsonl"

NATIVE = ("der", "die", "das", "und", "ein", "eine", "einen", "den", "dem",
          "des", "ist", "sind", "nicht", "mit", "für", "auf", "von", "zu",
          "sich", "dich", "euch", "ihr")
ENGLISH_STOPWORDS = ("the", "and", "you", "your", "with", "from", "that",
                     "this", "have", "will", "they", "them", "been", "must",
                     "into", "there", "their", "what", "when", "would")


def english_by_id(path):
    rows = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                quest = json.loads(line)
            except Exception:
                continue
            rows[str(quest.get("id"))] = quest
    return rows


def untranslated(text, reference):
    """Is this field the English text rather than the German?

    Not always byte-identical: an untranslated row often carries the English
    paragraph with a line of locale boilerplate appended after it. So
    containment counts, guarded by two conditions that keep a short English
    fragment inside real German prose from tripping it -- the reference has to
    be long enough to mean something, and it has to make up most of the field.
    """
    text = (text or "").strip()
    reference = (reference or "").strip()
    if not text or not reference:
        return False
    if text == reference:
        return True
    return (len(reference) >= 12 and reference in text
            and len(reference) >= 0.6 * len(text))


def reads_as_english(words):
    """Second test, for rows our English copy does not cover.

    Real German prose of any length carries der, die, und, ist; English prose
    carries the, and, you, with. The margin is deliberately wide -- three or
    more English function words and more than twice as many as German ones --
    so a quest that quotes an English name in a German sentence is left alone.
    """
    if len(words) < 8:
        return False
    english = sum(1 for w in words if w in ENGLISH_STOPWORDS)
    home = sum(1 for w in words if w in NATIVE)
    return english >= 3 and english > 2 * home


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--english", default=str(ENGLISH))
    parser.add_argument("--keep-english", action="store_true",
                        help="do not skip untranslated fields (for comparison)")
    args = parser.parse_args()
    english = {} if args.keep_english else english_by_id(pathlib.Path(args.english))

    counts = collections.Counter()
    forms = collections.defaultdict(collections.Counter)
    contexts = {}
    skipped = 0
    for line in (ROOT / "Data/cache/quests_deDE.jsonl").read_text(
            encoding="utf-8").splitlines():
        q = json.loads(line)
        reference = english.get(str(q.get("id")), {})
        # progress and reward only ever arrive via import_harvest.py -- the quest
        # API publishes neither, and objectives comes back empty from it too.
        for field in ("title", "description", "objectives", "progress",
                      "completion", "reward"):
            text = q.get(field) or ""
            if untranslated(text, reference.get(field)):
                skipped += 1
                continue
            words = TOKEN.findall(text)
            if not args.keep_english and reads_as_english(
                    [w.casefold() for w in words]):
                skipped += 1
                continue
            for word in words:
                if len(word) < 2:
                    continue
                key = word.casefold()
                counts[key] += 1
                forms[key][word] += 1
                contexts.setdefault(key, text[:500])

    out = ROOT / "Data/cache/wordlist_deDE.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for key in sorted(counts):
            word = forms[key].most_common(1)[0][0]
            f.write(json.dumps({"key": key, "word": word, "count": counts[key],
                                "context": contexts[key]},
                               ensure_ascii=False) + "\n")
    print(f"words={len(counts)} untranslated_fields_skipped={skipped} output={out}")


if __name__ == "__main__":
    main()
