# QuestWordHunter — German Dictionary

Learning German from quests is great until you spend half the session looking up *Stacheleber* and *Zuflucht*.

This is a ready-made German→English glossary built from real quest text, so the words you click already have a meaning waiting.

<img width="1399" height="1156" alt="German dictionary in the quest panel" src="https://github.com/user-attachments/assets/0368d63e-46c6-4f89-89a3-09f5dcca8bd9" />

## Hand-checked core

The original **73,863** Retail words were read against the quest sentence they appear in — not machine output. The pack now holds **121,853** entries. Its previous **104,295** entries are preserved, with **17,558** incremental entries from the expanded public corpus added on top. The new entries use filtered machine glosses, unambiguous DE/EN source names and contextual corrections; they have not all received individual human semantic review.

`Höllenhorde` is Fel Horde, not "Hell Horde". `bekommen` means to receive, never to become. `hinter'm` is "behind the", not "behind me".

## It speaks, too

Click a recorded word and hear it said. **104,295 recordings** cover the original entries,
read from German by a neural voice and checked one by one against the word
they were asked for. The reader is in this addon — five Lua files and
`sounds/` — so there is nothing else to install and no separate engine to
find.

The 17,558 new glossary entries do not yet have generated word recordings. Adding dictionary translations does not generate audio.

If you have the older separate downloads, remove them: the *German Voiceover*
engine addon and the *Voiceover: Words* pack are both inside this one now, and
two packs claiming the same words is not defined.

Quest narration is a different thing and still comes in its own packs, one per
group of expansions — this covers single words only.

## German quest library

Classic Era and Forever quest texts are included in `QuestData/`, in German
and English for comparison. No separate QuestData addon is needed. With the
base addon's quest library, completed quests can be reopened to click and
learn their words; its DE/EN selector keeps vocabulary in the chosen language.

Forever has 4,267 German titles, including 3,592 quests with German descriptions
and/or objectives. Missing passages stay explicitly unavailable or labelled
as English references. The pinned Classic texts are complemented by native
Forever cache records; quest 783 uses the original version without the later
Retail Deathwing text. The original native text collected by the base addon
has priority. See `QuestData/NOTICE` for the MIT source attribution.

The dictionary loads after an installed English Quest Panel, so its old quest
chunks cannot overwrite the authoritative Classic/Forever English records.

The library's source button also opens separate MultiLanguage quest editions
and Classic item, spell and NPC references, all inside this dictionary addon.
The current client's quest edition loads; Forever does not retain the Retail
or TBC source tables. Source editions include historical and seasonal material
and may differ between DE/EN. They remain separate from game observations.
Items/spells show static source prose, and NPCs provide names and roles.
Use DE/EN and click German words in the same learning reader. See QuestData
and EntityData notices/manifests for provenance and omitted fields.

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

Reviewed entries live in `Data/CuratedDE.jsonl` and override the machine output. Commit the generated `Data/DictionaryDE.lua`; do not commit `Data/cache/`.

For an incremental public-corpus run, `Tools/translate_incremental.py` extracts missing keys with the addon's actual Lua tokenizer. Classify names, English residue and ambiguous legacy self-glosses before running `translate --allow-network`. Publish all source/code updates first. The resumable translation cache and review queue stay outside the addon. `merge` appends accepted/revised entries after checking runtime keys; it preserves existing dictionary bytes and refuses conflicting curated replacements. New machine glosses still need contextual quality review and do not create new voice clips.

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
