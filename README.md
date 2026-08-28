# QuestWordHunter — German Dictionary

Learning German from quests is great until you spend half the session looking up *Stacheleber* and *Zuflucht*. This pack is a ready-made German→English glossary built from actual quest text, so common (and very long) words already have a gloss when you click them.

It plugs into [QuestWordHunter](https://github.com/Ironship/WordHunterWoW). Words stay in the pack — they are not copied into your SavedVariables. You can still change a translation; **Reset to dictionary** puts the pack wording back.

<img width="1399" height="1156" alt="{E7E7321A-9B7E-4D45-9D50-E94F790638EF}" src="https://github.com/user-attachments/assets/0368d63e-46c6-4f89-89a3-09f5dcca8bd9" />

~74,000 entries. Of those, 45,214 (61%) have been reviewed by hand against the quest sentence they appear in: the translation checked for false friends, wrong senses and missed official WoW names, and a short note added where the word teaches something — a compound broken up, a separable verb, a case a preposition takes. The rest is still raw Google output and is being worked through.

## What you need

- Retail 12.1 (`Interface 120100`)
- [QuestWordHunter](https://github.com/Ironship/WordHunterWoW)
- Target language set to **German**

Want English quest text on the side as well? That is a separate addon: [English Quest Panel](https://github.com/Ironship/WordHunterWoW-ENPanel).

## Rebuild (maintainers)

1. `Tools/keys.env` with Blizzard API keys. Never commit it.
2. Wago `QuestV2.csv` → `Data/QuestV2.csv` (gitignored).
3. `python Tools/fetch_quests.py`
4. `python Tools/build_wordlist.py`
5. `python Tools/translate_google.py --workers 4 --interval 0.25`
6. `python Tools/build_dictionary_lua.py`

Do not commit `Data/cache/` or `QuestV2.csv`. Commit generated `Data/DictionaryDE.lua`.

Another locale pack: copy this addon, change the locale in fetch/bootstrap, rebuild, register with `RegisterDictionaryProvider("<locale>", addonName, entries)`.

All rights reserved.
