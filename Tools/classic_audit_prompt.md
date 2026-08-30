# German dictionary audit — Classic Era words

You are improving a German→English dictionary used by a World of Warcraft addon.
Players read German quest text and click a word to see its English meaning plus a
short note. Your job is to fix machine-translation errors and write notes that
teach the reader something worth knowing.

## Input

`Data/cache/classic/audit_work/in/batch_NN.jsonl` — one JSON object per line:

- `key` — lowercase lookup key. **Copy it through byte for byte.** It is already
  casefolded the way the addon looks words up: `ß` is written `ss`, so
  `übergroßen` has the key `übergrossen`. Umlauts, however, stay as they are:
  the key is `höchstgeschwindigkeit`, never `hoechstgeschwindigkeit`. Do not
  "restore" the `ß`, do not ASCII-fold `ä ö ü`, do not re-case, do not fix what
  looks like a typo. Copy the key and the word exactly as given -- a changed
  key breaks the lookup, and a changed word breaks the repair path that would
  otherwise recover it.
- `word` — the German word as it appears in game. **Copy through verbatim.**
- `current` — the existing Google Translate output. Often right, sometimes wrong.
- `count` — how often the word occurs across all quests.
- `context` — a real quest sentence containing the word.

## Output

`Data/cache/classic/audit_work/out/batch_NN.jsonl` — one JSON object per input line,
**same order, same count, same keys**, with exactly these four fields:

```json
{"key":"eisenschmiede","word":"Eisenschmiede","translation":"Ironforge","note":"literally iron+forge; the dwarven capital, not a smith"}
```

Write the file with the Write tool. UTF-8, no BOM, no trailing commas, no
markdown fences, one compact JSON object per line.

## Do both jobs in one pass

The two halves of this task are the translation and the note, and they carry
equal weight. Agents on this task reliably do one and skip the other: a pass
told to care about notes stops touching translations, and a pass told to care
about translations writes four notes in a hundred and fifty rows. Both get
rejected and rerun.

A healthy pass revises **around a third of the translations** and leaves
**a note on nearly every row**. Check your own output against that before you
finish. If either number is far below, you have not done the work yet.

The one honest reason for a low note count is a batch thick with bare proper
names -- NPC names, surnames -- where an empty note is correct because you must
not invent lore. That is the only excuse. Every compound, verb, adjective and
common noun gets a real note.

## What is different about this batch

These words come from Classic Era quest text, not from the modern game. Two
things follow from that.

**The German client leaves many English names untranslated.** Ironforge,
Stormwind, Undercity, Booty Bay, Crossroads, Winterspring and the like appear
verbatim in the German text. When the German word already *is* the English
name, the translation is that same name, unchanged, and the note should say
what it is rather than pretending a translation happened -- or be empty if
there is nothing to say. Do not "translate" Ironforge into Iron Forge.

**Objective lines are imperative and formal.** `Bringt`, `Tötet`, `Sammelt`,
`Kehrt zurück` are second-person plural commands, the polite form the game
addresses the player with. Translate the verb as a bare infinitive as usual --
`bringen` → bring -- and do not carry the -t ending into English as a past
tense.

Old zone and creature names are the place where invented lore does the most
damage here. If you are not certain an official English name exists, give the
literal reading. A literal translation that is honest beats a confident name
that is wrong.

## Errors to look for before you accept `current`

Google is right often enough that skimming feels safe. These are the mistakes
it actually makes here:

- a comparative or superlative flattened to the base form, or the reverse
  (`größer` is "bigger", not "big")
- a participle handed back as an infinitive (`getraut` is "dared" -- not "to
  dare", and not "married")
- a common noun still capitalised in English because German capitalises nouns
- an official English WoW name missed (`Höllenhorde` is Fel Horde, not
  "Hellhorde")
- a false friend taken at face value (`bekommen` is "receive", never "become")
- the wrong sense of an ambiguous word (`Bug` is a ship's bow here, not an insect)
- a plural rendered as a singular, or the reverse
- a contraction misread (`hinter'm` is "behind the", not "behind me")

## translation

- Give the meaning that fits **WoW quest text**, not a dictionary's first entry.
- Use the **official English WoW term** when the German is a game proper noun:
  `Eisenschmiede` → Ironforge (not "Ironsmith"), `Dracheninseln` → Dragon Isles
  (not "Dragon Islands"), `Sturmwind` → Stormwind.
- If you are not confident an official English name exists, give a clean literal
  translation instead. **Do not invent lore, zone names, or NPC names.**
- Separate genuinely distinct senses with `; ` — at most three, most common first.
- Keep the grammatical category of the German word (noun → noun, verb → verb).
  Nouns: no article. Verbs: bare infinitive without "to" unless it disambiguates.
- Match the source's capitalisation habit: proper nouns capitalised, common nouns
  lowercase, even though German capitalises every noun.
- If `current` is already the best answer, repeat it unchanged. That is a normal
  and expected outcome — do not change things just to look busy.

## note

This is the part the user actually reads for fun. Make it earn its place.

Pick whichever of these applies, best first:

1. **Compound breakdown**, when it illuminates the word:
   `Dunkelheit` → "dunkel (dark) + -heit, the suffix that turns adjectives into nouns"
2. **False friend / trap**, when a learner would guess wrong:
   `bekommen` → "false friend: means to receive, never to become"
3. **Official name differs from the literal sense**:
   `Schattenhammer` → "literally shadow-hammer; the English name is Twilight's Hammer"
4. **Idiom or fixed phrase** the word usually appears in:
   `heißen` → "willkommen heißen = to welcome"
5. **Etymology or a genuinely interesting fact** about the word.

Rules:

- English, lowercase start, **no trailing period**, at most ~120 characters.
- Never merely restate the translation ("means darkness") — that is wasted space.
- Never write filler like "compound noun" or "common German word" on its own.
- Prefer concrete over vague. "from Old High German *hari* (army)" beats
  "has an interesting history".
- If nothing worth saying comes to mind, use `""`. An empty note is much better
  than a boring one.
- No newlines, no quotes-inside-quotes problems — keep it plain.

## Accuracy

Getting a translation wrong is worse than leaving it as it was. When torn between
a confident literal reading and a half-remembered WoW term, choose the literal
one. Do not guess at lore.

Return only a one-line summary: how many rows you wrote, and any keys you were
genuinely unsure about.
