# MultiLanguage Classic learning references

This pack stores names, full tooltip prose, and NPC roles under the explicit source namespace `WordHunterWoW_EntityDataBySource["multilanguage-classic"]`. It does not register with ENPanel, replace item/spell names in the game, or modify the word dictionary or native quest data.

Schema: `ref.kinds[kind][locale][id]`, where kind is `item`, `spell`, or `npc`, and locale is `deDE` or `enUS`. Each row has `name` and optional `text` or `role`. Names are stored once; the learning reader combines the name and prose so both are clickable. Some IDs have only one locale. Metadata reports all locale counts, paired counts, and one-sided counts.

`referenceOnly=true` applies to the whole pack: source Classic data includes seasonal additions and static numerical values that are not verified against Forever or the player's current tooltip. `unresolvedValues=true` additionally marks rows whose source numeric formulas/macros were replaced with `[Quellwert]` or `[source value]`. Source formulas are never evaluated into invented gameplay values. Null-only text is omitted; names and other useful prose remain.

Quality/color tokens and tooltip column braces are removed from the display text. Normalization preserves prose, line breaks, German umlauts, readable bracketed instructions, and both gender alternatives. Standard name/race/class placeholders remain as `{name}`, `{race}`, `{class}`. No word is automatically added to the learner's saved list.

Load `Metadata.lua` first and then the files in `source-manifest.json` → `runtime_load_order`. Only those 131 files belong in the addon manifest. These paths are relative to the addon root and already begin with `EntityData/`. `Source/`, `Tools/`, and `tests/` are maintainer artifacts and do not load in the game.

Explicit developer names and one copied English German-locale prose field are excluded from learning rows. The manifest lists every exclusion; raw archives retain the original material. Ordinary words such as Radius and legitimate Test of quest/item names are preserved.

The six original DE/EN Lua source files are preserved byte-for-byte in deterministic gzip archives under `Source/`. Their original and compressed SHA-256 values, immutable upstream URLs, source commit, source license, and the project owner's reported author permission are recorded in `source-manifest.json`. Upstream's `All rights reserved` license statement is preserved; the import does not invent an open-source grant.

Rebuild from bundled archives, from the containing addon directory:

```text
python EntityData/Tools/import_entities.py --corpus ../artifacts/reference-entity-corpus.jsonl
```

To rebuild from the original checkout, add `--source <MultiLanguage-checkout>`. The generator requires pinned commit `c51dc2e5141f070f5b92de190521d79e8dccaeab` with unchanged entity files. The build-time reader needs a Lua executable; it supports Lua 5.1 and newer. Generated runtime files use Lua 5.1 syntax.

`reference-entity-corpus.jsonl` is an optional external normalized text inventory. Rows identify locale, ID, kind, explicit source flavor, field category (`name`, `text`, `role`), and text. It is suitable for checking word coverage, with names kept distinct from ordinary prose. It is not a translation output.

Validation loads every chunk with Lua 5.1, checks counts and one-sided records, checks meaningful German/name/role samples, and confirms that dictionary, English item, and native quest table sentinels remain untouched. All runtime files are also compiled with `luac5.1 -p`. Rebuilding the same files and corpus from the bundled archives with Lua 5.1 produces identical bytes. No game UI validation is claimed by these checks.
