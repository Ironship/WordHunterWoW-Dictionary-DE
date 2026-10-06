# MultiLanguage entity learning references

This pack stores names, full tooltip prose, and NPC roles under the explicit source namespace `WordHunterWoW_EntityDataBySource["multilanguage-classic"]`. It does not register with ENPanel, replace item/spell names in the game, or modify the word dictionary or native quest data.

Schema: `ref.kinds[kind][locale][id]`, where kind is `item`, `spell`, or `npc`, and locale is `deDE` or `enUS`. Each row has `name` and optional `text` or `role`. Names are stored once; the learning reader combines the name and prose so both are clickable. Some IDs have only one locale. Metadata reports all locale counts, paired counts, and one-sided counts.

`referenceOnly=true` applies to the whole pack: source Classic data includes seasonal additions and static numerical values that are not verified against Forever or the player's current tooltip. `unresolvedValues=true` additionally marks rows whose source numeric formulas/macros were replaced with `[Quellwert]` or `[source value]`. Source formulas are never evaluated into invented gameplay values. Null-only text is omitted; names and other useful prose remain.

Quality/color tokens and tooltip column braces are removed from the display text. Normalization preserves prose, line breaks, German umlauts, readable bracketed instructions, and both gender alternatives. Standard name/race/class placeholders remain as `{name}`, `{race}`, `{class}`. No word is automatically added to the learner's saved list.

Load files in `source-manifest.json` → `runtime_load_order`, in that exact order. This includes the unchanged 131 Classic runtime files and the guarded edition files listed below. Only the listed files belong in the addon manifest. These paths are relative to the addon root and already begin with `EntityData/`. `Source/`, `Tools/`, and `tests/` are maintainer artifacts and do not load in the game.

Explicit developer names and one copied English German-locale prose field are excluded from learning rows. The manifest lists every exclusion; raw archives retain the original material. Ordinary words such as Radius and legitimate Test of quest/item names are preserved.

The six original DE/EN Lua source files are preserved byte-for-byte in deterministic gzip archives under `Source/`. Their original and compressed SHA-256 values, immutable upstream URLs, source commit, source license, and the project owner's reported author permission are recorded in `source-manifest.json`. Upstream's `All rights reserved` license statement is preserved; the import does not invent an open-source grant.

Additional editions use separate source buckets: `multilanguage-tbc`, `multilanguage-retail`, `multilanguage-wrath`, `multilanguage-cata`, `multilanguage-mop-classic`, and `multilanguage-forever`. They retain source-local names and static prose even when IDs overlap. Per-locale repository, branch or historical snapshot label, immutable commit and interface are recorded in metadata and the manifest. The German source repository's current `master` is Cata (Interface 40402); it is never presented as German Wrath. German Wrath comes from the authentic historical commit `a0a5e66931a7f13f06e4f73d1dd472215c5da5a9`, titled "Last WOTLK version before moving to CATA" (2024-05-04, Interface 30403). Matching IDs identify paired names; they do not establish that source locales were exported from identical patches.

Classic visibility remains unchanged. New TBC/Wrath/Cata/MoP metadata activates only on a known non-Retail flavor with a matching 2.x/3.x/4.x/5.x client version. Retail activates only for `Compat.GameFlavor()=="retail"`, Forever only for `"forever"`. Unknown flavor or malformed client version fails closed. Skipped editions do not create source tables; every generated chunk returns before constructing records when its metadata bucket is absent. This prevents foreign editions from allocating their large data tables on each client.

Pinned upstream TOC order determines source coverage and shard precedence. In Retail, itemsFour deliberately replaces earlier values for IDs 198998 and 198999; both overlapping IDs and changed values are recorded per source file. An orphaned Forever spellsSix file is actually an EN Retail blob and is absent from the Forever TOC, so it is excluded with explicit provenance rather than guessed to be Forever content. Retail's EN ninth spell shard is imported; German upstream has eight shards.

The new source catalog is `Source/Variants/source-catalog.json`. Original payloads, loaders, TOCs and available upstream license files are stored once per distinct SHA-256 as deterministic gzip blobs under `Source/Variants/`. The external input inventory uses the same blobs; hard links avoid a second physical copy where the filesystem permits. Every raw source is verified against the pinned Git blob SHA-1 and byte length when downloaded, then against raw and compressed SHA-256 on rebuild. New developer filtering additionally omits explicit GM-only/zzOLD retired labels; ordinary Training Dummy and Test of names remain. German fields with positive long-English prose evidence are omitted while useful names and other fields remain.

Rebuild the six new editions from bundled archives, from the containing addon directory. This verifies all Classic generated hashes and preserves those files byte-for-byte:

```text
python EntityData/Tools/import_variants.py --corpus ../artifacts/normalized-entity-corpus.jsonl --lua-command lua5.1
```

To fetch the pinned sources again, add `--fetch --inputs <external-input-folder>` before the final `--lua-command` option. On Windows with Debian WSL use `--lua-command wsl -d Debian -e lua5.1`. The build-time source reader uses an isolated Lua environment and never runs upstream addon UI code. The legacy `import_entities.py` builds Classic alone before variants are installed; it refuses to discard an existing variant manifest. All generated runtime files use Lua 5.1 syntax.

`reference-entity-corpus.jsonl` is the preserved Classic normalized inventory; `normalized-entity-corpus.jsonl` contains the six new editions. These are external normalized text inventories. Rows identify locale, ID, kind, explicit source flavor, field category (`name`, `text`, `role`), and text. It is suitable for checking word coverage, with names kept distinct from ordinary prose. It is not a translation output.

Validation loads every chunk with Lua 5.1, checks counts and one-sided records, checks meaningful German/name/role samples, and confirms that dictionary, English item, and native quest table sentinels remain untouched. All runtime files are also compiled with `luac5.1 -p`. Rebuilding the same files and corpus from the bundled archives with Lua 5.1 produces identical bytes. No game UI validation is claimed by these checks.

Run validation from the addon root:

```text
python EntityData/tests/test_variants.py
lua5.1 EntityData/tests/data.test.lua .
lua5.1 EntityData/tests/variants.test.lua . retail
```

Repeat the last command for `tbc`, `wrath`, `cata`, `mop-classic`, `forever`, `era`, `sod`, `unavailable`, `unknown`, `unknown-flavor`, `numeric-flavor`, `numeric-version`, `malformed-version`, `malformed-major` and `retail-major-two`. Each process loads only Classic plus the matching edition, verifies complete counts/paired coverage, source-ID isolation, actual later-shard duplicate values, source formatting and unchanged dictionary/native tables. A full second build must produce the same manifest, runtime hashes, archives and normalized corpus bytes.
