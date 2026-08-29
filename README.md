# QuestWordHunter — German Dictionary

Learning German from quests is great until you spend half the session looking up *Stacheleber* and *Zuflucht*.

This is a ready-made German→English glossary built from real quest text, so the words you click already have a meaning waiting.

<img width="1399" height="1156" alt="German dictionary in the quest panel" src="https://github.com/user-attachments/assets/0368d63e-46c6-4f89-89a3-09f5dcca8bd9" />

## Every entry is checked by hand

All **73,863 words**. Not machine output — each one was read against the quest sentence it appears in, the meaning corrected where a translator got it wrong, and a short note added where the word teaches you something: a compound pulled apart, a false friend, the case a preposition takes.

`Höllenhorde` is Fel Horde, not "Hell Horde". `bekommen` means to receive, never to become. `hinter'm` is "behind the", not "behind me".

## Install

Unzip into `_retail_\Interface\AddOns\` and restart the game.

You need:

- [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) **1.6.0 or newer**
- Target language set to **German**

Words stay in the pack and are not copied into your saved data. Change any translation you like — your version wins, and **Reset to dictionary** brings this one back.

## Other languages

There are packs for [French](https://github.com/Ironship/WordHunterWoW-Dictionary-FR), [Spanish](https://github.com/Ironship/WordHunterWoW-Dictionary-ES), [Italian](https://github.com/Ironship/WordHunterWoW-Dictionary-IT) and [Portuguese](https://github.com/Ironship/WordHunterWoW-Dictionary-PTBR) too. They are machine-translated — only this one has been checked by hand.

Want English quest text beside the original as well? That is [English Quest Panel](https://github.com/Ironship/WordHunterWoW-ENPanel).

Retail 12.1. All rights reserved.

## Rebuild (maintainers)

Blizzard API keys in `Tools/keys.env`, then:

```
python Tools/fetch_quests.py
python Tools/build_wordlist.py
python Tools/translate_google.py --workers 4 --interval 0.25
python Tools/build_dictionary_lua.py
```

Hand-checked entries live in `Data/CuratedDE.jsonl` and override the machine output. Commit the generated `Data/DictionaryDE.lua`; do not commit `Data/cache/`.
