# German Dictionary: quest data

German and English quest text bundled in WordHunterWoW-Dictionary-DE for
Classic Era and Forever. This directory is data inside the dictionary addon,
with no separate addon, settings or SavedVariables.

Each language has 4,244 Classic quest records from the pinned pfQuest Vanilla
dataset. On Forever these records are copied into a separate compatibility
bucket, then replaced by 65 native German and 127 native English cached quest
records. The resulting Forever catalogs contain 4,267 German and 4,294 English
quests. Some old records contain a title without an opening description; an
absent passage is left empty.

The German Classic records contain 3,565 descriptions and 3,568 objective
passages. The English Classic records contain 3,582 descriptions and 3,586
objective passages. NPC progress and hand-in passages are not supplied by this
source and are not invented. Twenty-two untranslated English descriptions and
objective passages in the German source are left empty; their IDs are recorded
in the manifest.

Native quests archived by the base addon take precedence over the static pack.
Native Forever cache data here affects only Forever. There is no Retail bucket,
and the loader leaves the Retail English panel dataset unchanged.

Install WordHunterWoW-Dictionary-DE as usual. Its manifests load these files
after WordHunterWoW and, when present, WordHunterWoW-ENPanel. The final loader
selects the matching Classic or Forever English table so an old Retail backfill
cannot supply Deathwing's version of quest 783 on Forever.

See `NOTICE`, `LICENSE`, and `source-manifest.json` for the exact source revision,
counts, cache builds, and content hashes. Data is exported in chunks of at most
250 records and uses Lua 5.1 syntax.

Rebuild using `Tools/build_quest_data.py`, selecting the source JSONL files,
4,244-ID allowlist, captured native WDB files, original pfQuest license, and a
destination via its required `--classic-de`, `--classic-en`, `--classic-ids`,
`--wdb-de`, `--wdb-en`, `--license`, and `--out` arguments. The script only reads
the input files. It accepts the validated Forever 70xxx build family and rejects
invalid framing, duplicate IDs, ambiguous text tails, and invalid UTF-8.
