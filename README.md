# QuestWordHunter — German Dictionary

Learning German from quests is great until you spend half the session looking up *Stacheleber* and *Zuflucht*.

This is a ready-made German→English glossary built from real quest text, so the words you click already have a meaning waiting.

<img width="1399" height="1156" alt="German dictionary in the quest panel" src="https://github.com/user-attachments/assets/0368d63e-46c6-4f89-89a3-09f5dcca8bd9" />

## Hand-checked core

The original **73,863** Retail words were read against the quest sentence they appear in — not machine output. The pack now holds **104,295** entries: Classic-only vocabulary and words collected in game sit on top of that reviewed core.

`Höllenhorde` is Fel Horde, not "Hell Horde". `bekommen` means to receive, never to become. `hinter'm` is "behind the", not "behind me".

## It speaks, too

Click a word and hear it said. **104,295 recordings**, one for every entry,
read from German by a neural voice and checked one by one against the word
they were asked for. The reader is in this addon — five Lua files and
`sounds/` — so there is nothing else to install and no separate engine to
find.

If you have the older separate downloads, remove them: the *German Voiceover*
engine addon and the *Voiceover: Words* pack are both inside this one now, and
two packs claiming the same words is not defined.

Quest narration is a different thing and still comes in its own packs, one per
group of expansions — this covers single words only.

## Install

Unzip into `_retail_\Interface\AddOns\` and restart the game. It is about
816 MB, nearly all of it the recordings.

You need:

- [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) **1.6.0 or newer**
- Target language set to **German**

Words stay in the pack and are not copied into your saved data. Change any translation you like — your version wins, and **Reset to dictionary** brings this one back.

## Other languages

There are packs for [French](https://github.com/Ironship/WordHunterWoW-Dictionary-FR), [Spanish](https://github.com/Ironship/WordHunterWoW-Dictionary-ES), [Italian](https://github.com/Ironship/WordHunterWoW-Dictionary-IT) and [Portuguese](https://github.com/Ironship/WordHunterWoW-Dictionary-PTBR) too. They are machine-translated — only this one has been checked by hand.

Want English quest text beside the original as well? That is [English Quest Panel](https://github.com/Ironship/WordHunterWoW-ENPanel).

Retail 12.1, Classic Era and World of Warcraft: Forever. GPL v3 — see
`LICENSE`; the audio carries CC BY-NC 4.0, which `NOTICE` sets out.

## Where the audio comes from, and the one rule about it

The master is [WordHunterWoW-Voice-DE-Words](https://github.com/Ironship/WordHunterWoW-Voice-DE-Words),
which is what the repair passes write to. The copy here is assembled by
`Tools/put_voice_in_dictionary.py` in the workspace, which also writes
`Part.lua` and both manifests.

So the same recordings live in two repositories, and a clip repaired in one
and not the other is a fault nothing reports — the word simply says something
other than the corpus says it should. **After any repair pass, run that tool
again with `--sync`.** It copies only what differs, removes what the master no
longer has, and checks 300 dictionary words against the path the engine would
ask for before it finishes.

## Rebuild (maintainers)

Blizzard API keys in `Tools/keys.env`, then:

```
python Tools/fetch_quests.py
python Tools/build_wordlist.py
python Tools/translate_google.py --workers 4 --interval 0.25
python Tools/build_dictionary_lua.py
```

Hand-checked entries live in `Data/CuratedDE.jsonl` and override the machine output. Commit the generated `Data/DictionaryDE.lua`; do not commit `Data/cache/`.

## Classic Era words

Words that only appear in Classic Era quest text are gathered separately, so a
Classic run can never write into the Retail cache:

```
python Tools/extract_classic_words.py --quests <quests.jsonl>
python Tools/translate_google.py --wordlist Data/cache/classic/wordlist_deDE.jsonl --cache Data/cache/classic/translations_de_en.jsonl
python Tools/prepare_classic_audit.py --limit 4200 --batch-size 150
# audit the batches, then:
python Tools/check_audit_effort.py --workdir Data/cache/classic/audit_work
python Tools/merge_audit.py --workdir Data/cache/classic/audit_work
python Tools/build_dictionary_lua.py
```

Everything ends up in the same `CuratedDE.jsonl` and the same
`DictionaryDE.lua`: the dictionary is keyed by word, so one file is correct for
both games.

## Licence

GPL v3 — see `LICENSE`, and `NOTICE` for the attribution the licence requires.
