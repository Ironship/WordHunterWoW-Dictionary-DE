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
objective passages. NPC progress and hand-in passages are not supplied by
pfQuest and are not invented. Twenty-two untranslated English descriptions and
objective passages in the German source are left empty; their IDs are recorded
in the manifest.

An additive MultiLanguage import supplies 1,873 bilingual progress passages and
2,707 bilingual hand-in passages on Classic. Forever receives 1,872 progress
and 2,706 hand-in passages from that Classic source as an explicit compatibility
fallback. Only existing quest IDs whose opening passages match in both languages
and whose candidate dialogue is unflagged are included. This checks compatibility
against the bundled corpus; it does not certify every passage against a live
client. Three DE-only progress fragments and all source-only quest IDs are omitted.

Seven German descriptions and seven German objective lines are also filled where
the existing field is empty: quests 7221, 7222, 7704, 8290, 8295, 8856, and 8869.
Only audited empty reward headings or an exact duplicated description suffix are
removed. English counterparts corroborate these fills. No existing wording,
native Forever record metadata, or dictionary vocabulary entry is replaced.
Per-field `Source` and `SourceFlavor` metadata distinguishes imported dialogue
from native opening text. Classic and Forever records remain separate tables.

The import decodes HTML and scalar name/class/race placeholders, converts
nonbreaking spaces to ordinary spaces, and repairs two reviewed missing sentence
spaces (quests 8517 and 9002). Emotes and gender alternatives remain intact.

Native quests archived by the base addon take precedence over the static pack.
Native Forever cache data here affects only Forever. The default flavor-qualified
catalog has no Retail bucket, and its loader leaves the Retail English panel
dataset unchanged.

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

After rebuilding the base, reproduce the additive import from the immutable
2026-10-05 audit directory (source Lua files, JSONL exports, and reviewed opening
fills) with:

```
python QuestData/Tools/import_multilanguage_quests.py --audit PATH_TO_AUDIT --out QuestData
```

The importer checks every pinned input SHA256 before writing, keeps nonempty
fields, writes the load order into both manifests, and can write the exact accepted
payload outside the addon with `--selection PATH_TO_JSON`. It does not fetch data,
run a dictionary translator, read player SavedVariables, or install into a client.

The remaining usable source material is available through seven separate
reference libraries: MultiLanguage Classic master (including seasonal material),
TBC, Wrath, Cataclysm, MoP Classic, Forever, and Retail. They live in `WordHunterWoW_QuestSources[sourceKey].locales`,
never in the native Classic/Forever tables. A reference must be explicitly
selected by the base addon's quest library. Source versions, IDs, and locale
revisions remain separate; a matching DE/EN ID does not certify matching passages.
Source records carry `sourceVersionUnverified`, `bilingualPairVerified = false`,
and `voiceUnavailable` metadata so a native audio clip cannot be presented as a
verified recording of a different source variant.

Client guards also apply to the source metadata. Classic master is available on
non-Retail clients (including Forever and SoD), Retail only on Retail, and TBC
only on non-Retail clients reporting version 2.x. Wrath, Cataclysm and MoP
Classic similarly require non-Retail versions 3.x, 4.x and 5.x. The separate
Forever branch is available only on Forever. Wrath German comes from the historical
last-WOTLK snapshot of MultiLanguage-de, whose upstream manifest reports Interface
30403. German text from a different edition is never relabeled as Wrath. The version
guards require a known Classic/SoD/Forever flavor and a numeric three-component
version; missing, numeric, malformed and unknown-flavor inputs leave these newer
libraries absent. The historical Classic-master guard is retained unchanged and
still admits a non-nil non-Retail flavor value. Unavailable source buckets are absent;
their text tables are not retained in memory. The source manifest still records
all packaged source files and input hashes across clients.

Opening descriptions, progress, and hand-in text remain distinct phases.
Objective text has an authentic `objectives` field only when the independently
bundled corpus corroborates the exact text in the same flavor and locale.
Other objective text is `sourceObjective`, an explicitly unverified source-field
phase; it is not silently appended to an offer as an authentic instruction.
If an objective exactly duplicates a displayed progress/completion/description
phase, the duplicate field is omitted and that phase retains the text.

Cleanup removes only an exact appended description or a trailing sequence of
known empty reward headings. Ambiguous reward concatenations, development/test
text, unresolved source controls, and German sentence fields identical to their
English counterpart after the same cleanup are excluded individually. Standard
`$gMale:Female;` gender macros remain literal for the shared reader's `UnitSex`
resolution; nested unknown controls are still quarantined. A captured numeric German title
is omitted while the record's usable German passages remain. Rewards/item lists
are outside this quest-reading corpus. The full exclusion/recovery lists and
counts are in `source-manifest.json.referenceSources`.

Reproduce these libraries after the default compatibility import with:

```
python QuestData/Tools/export_multilanguage_references.py --inputs PATH_TO_NEXT_QUEST_INPUTS
python QuestData/Tools/import_multilanguage_references.py --audit PATH_TO_AUDIT --next-inputs PATH_TO_NEXT_QUEST_INPUTS --out QuestData --report IMPORT_REPORT.json --corpus ACCEPTED_CORPUS.jsonl
python QuestData/Tools/check_reference_import.py --audit PATH_TO_AUDIT --next-inputs PATH_TO_NEXT_QUEST_INPUTS --questdata QuestData --corpus ACCEPTED_CORPUS.jsonl
```

`--report PATH_TO_JSON` writes full source/exclusion evidence outside the addon;
`--corpus PATH_TO_JSONL` writes accepted normalized fields for an incremental
vocabulary-gap check. Neither option translates a word or modifies the existing
dictionary. `referenceSources.files` provides the exact load order, with
`ReferenceMetadata.lua` preceding guarded `References/*` chunks.

The 2026-10-06 batch keeps the original 2026-10-05 audit immutable. Its raw Lua,
pinned trees, direct upstream TOC loader evidence, source/export provenance,
branch comparison and accepted corpus live in the delivery folder's
`development-inputs/multilanguage-next-20261006/quests`. The optional exporter
requires `lupa` with Lua 5.1 and runs only hash-verified literals in a restricted
environment without IO, OS, require or game APIs. The importer itself uses the
Python standard library. Omitting `--next-inputs` reproduces the historical
three-source snapshot; include it to build the current seven-source package.

Retail English revision `fb8e7e9117b5c99347d05ec8a30b0644fbef4fb8` adds 887
raw quest IDs to the prior 48,076: 48,963 total. Of those, 881 usable records
enter the source library; six development/unused records remain excluded. No old raw row changed or
vanished, and every previously accepted ID and passage is preserved. German
Retail remains at its separate revision. The source revisions carry different
upstream client interfaces and are not certified bilingual versions.

Forever's German source is byte-identical to Classic master, while its English
branch has distinct IDs and wording. Both retain their exact branch provenance;
matching IDs never certify a native quest variant or an audio recording. New
Cataclysm and MoP German sources come from their own matching-edition repositories.
Wrath German uses revision `a0a5e66931a7f13f06e4f73d1dd472215c5da5a9`,
dated 4 May 2024 and explicitly described upstream as the last WOTLK version
before moving to Cataclysm. Its German and English revisions remain independent;
the edition evidence does not certify every bilingual passage or live-client wording.
Quest references retain `voiceUnavailable = true` even when a native quest with
the same ID has audio. Translation and word audio generation are separate later
steps after the import updates have been published.
