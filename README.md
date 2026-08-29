# QuestWordHunter — German Dictionary

Learning German from quests is great until you spend half the session looking up *Stacheleber* and *Zuflucht*. This pack is a ready-made German→English glossary built from actual quest text, so common (and very long) words already have a gloss when you click them.

It plugs into [QuestWordHunter](https://github.com/Ironship/WordHunterWoW). Words stay in the pack — they are not copied into your SavedVariables. You can still change a translation; **Reset to dictionary** puts the pack wording back.

<img width="1399" height="1156" alt="{E7E7321A-9B7E-4D45-9D50-E94F790638EF}" src="https://github.com/user-attachments/assets/0368d63e-46c6-4f89-89a3-09f5dcca8bd9" />

**All 73,863 entries have been reviewed by hand** against the quest sentence the word actually appears in: the translation checked for false friends, wrong senses of ambiguous words and missed official WoW names, and a short note added where the word teaches something — a compound broken apart, a separable verb, the case a preposition takes. Nothing in this pack is raw machine output any more.

## What you need

- Retail 12.1 (`Interface 120100`)
- [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) **1.6.0 or newer**
- Target language set to **German**

1.6.0 or newer matters: earlier versions lowercase only ASCII, so a word beginning with an accented capital — `Überfall`, `Ähnlich`, `Öffnet` — never matched a dictionary key and opened a second entry in your word list instead. That covers 2,925 occurrences across 466 words in this corpus.

Want English quest text on the side as well? That is a separate addon: [English Quest Panel](https://github.com/Ironship/WordHunterWoW-ENPanel).

Learning a different language? There are packs for [French](https://github.com/Ironship/WordHunterWoW-Dictionary-FR), [Spanish](https://github.com/Ironship/WordHunterWoW-Dictionary-ES), [Italian](https://github.com/Ironship/WordHunterWoW-Dictionary-IT) and [Portuguese (BR)](https://github.com/Ironship/WordHunterWoW-Dictionary-PTBR) too — though only this one has been through the review above.

## Rebuild (maintainers)

1. `Tools/keys.env` with Blizzard API keys. Never commit it.
2. A quest id list at `Data/quest_ids.csv` — one `ID` column. Gitignored.
3. `python Tools/fetch_quests.py`
4. `python Tools/build_wordlist.py`
5. `python Tools/translate_google.py --workers 4 --interval 0.25`
6. `python Tools/build_dictionary_lua.py`

Do not commit `Data/cache/` or `quest_ids.csv`. Commit generated `Data/DictionaryDE.lua`.

### Filling the gaps the API leaves

Blizzard's quest endpoint returns a title and the offer text only. `objectives`
comes back empty for all 30,815 quests, and there is no progress or hand-in
text and no NPC gossip at all, so a word living solely in one of those passages
can never enter this corpus. With **Collect quest and NPC text** enabled in
WordHunterWoW, `/whw harvest export` writes what a player has seen to
SavedVariables; fold it in with

```
python Tools/import_harvest.py --saved "<WoW>/_retail_/WTF/Account/<ACCT>/SavedVariables/WordHunterWoW.lua"
```

then rebuild from `build_wordlist.py` onward. Existing corpus text is never
overwritten -- only empty fields are filled.


Another locale pack: copy this addon, change the locale in fetch/bootstrap, rebuild, register with `RegisterDictionaryProvider("<locale>", addonName, entries)`.

All rights reserved.
