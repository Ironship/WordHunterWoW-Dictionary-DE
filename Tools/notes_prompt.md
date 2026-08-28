# German dictionary — notes-only pass

These entries were curated earlier, in a different pass, with a different voice.
Your job is to bring their **notes** into one house style. The translations were
checked by hand and are trusted.

## Hard rule

`key`, `word` and `translation` are **read-only**. Copy all three through byte for
byte, including `ß` written as `ss` in keys, and unusual capitalisation. If you
think a translation is wrong, leave it alone and say so in your final one-line
reply instead. Never edit it.

## Input

`Data/cache/notes_work/in/batch_NN.jsonl` — `key`, `word`, `translation`, the
existing `note`, and a `context` sentence from a quest.

## Output

`Data/cache/notes_work/out/batch_NN.jsonl` — same rows, same order, four fields:
`key`, `word`, `translation`, `note`. Write it with the Write tool. Compact JSON,
one object per line, UTF-8, no markdown fences.

## House style for `note`

- English, lowercase start unless the first word is a German word or a proper
  noun, **no trailing period**, at most ~120 characters, no newlines.
- Never restate the translation. "means darkness" is wasted space.
- Prefer, best first: compound breakdown that illuminates the word; false friend
  warning; a case where the official English WoW name differs from the literal
  sense; the fixed phrase or idiom the word lives in; a real etymology.
- `""` is a valid and good answer when nothing worth saying exists.

## What to change

- **Leave a good note alone.** Copy it through unchanged. Most already fit.
- **Upgrade a thin note.** `inflected form of monatlich` states the lemma, which
  is useful, but it can carry more: `inflected form of monatlich; from Monat
  (month) + -lich, the suffix behind English -ly`. Keep the lemma information —
  do not drop it — and add something.
- **Fix style only** where the content is fine but the shape is off (capitalised
  opener on an English word, trailing period, over-long).
- **Do not invent.** No made-up etymologies, no guessed WoW lore. If you cannot
  improve a note honestly, keep it as it is.

Reply with one line: how many rows you wrote, how many notes you actually
changed, and any translation you believe is wrong.
