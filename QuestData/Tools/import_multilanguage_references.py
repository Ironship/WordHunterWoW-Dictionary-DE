"""Build explicitly selected source-reference quest libraries, never native data.

Reads the pinned 2026-10-05 audit snapshots. Locale/era versions remain separate;
no dictionary translation, network access, SavedVariables or client installation.
"""
import argparse
import collections
import json
from pathlib import Path
import re

from build_quest_data import quote
from import_multilanguage_quests import clean, digest, normalized, read_rows, SPACING_REPAIRS

SPECS = {
    "classic": {"key": "multilanguage-classic-master", "label": "MultiLanguage Classic master (Era + seasonal)",
                "sourceFlavor": "classic-master", "snapshot": "MultiLanguage",
                "commits": {"deDE": "c51dc2e5141f070f5b92de190521d79e8dccaeab", "enUS": "c51dc2e5141f070f5b92de190521d79e8dccaeab"}},
    "tbc": {"key": "multilanguage-tbc", "label": "MultiLanguage TBC",
            "sourceFlavor": "tbc", "snapshot": "MultiLanguage-tbc",
            "commits": {"deDE": "fe999319f2c9c4c3cdd1bc60c8ae711c079b175f", "enUS": "fe999319f2c9c4c3cdd1bc60c8ae711c079b175f"}},
    "retail": {"key": "multilanguage-retail", "label": "MultiLanguage Retail",
               "sourceFlavor": "retail", "snapshot": "MultiLanguage-retail",
               "commits": {"deDE": "a54af98d3013271c6f2cac8c5c00bbf4d74185bd", "enUS": "b2e3b0bf1251f30babdb44545adf3957e94d63f6"}},
}
EXPORT_HASHES = {
    "ml-classic-de.jsonl": "c13daaccf5904609dba1a80a4dee1b7202ba98aee12cd48e8ed65c5d1a8cfc41",
    "ml-classic-en.jsonl": "5881f384c7873b9c204db449b5f9b884fe5a85a41cda9c62226ff27f53a45638",
    "ml-tbc-de.jsonl": "bebe670389c277d2def81486f063e5687125bf6c7f2139f9007a98c944bbc371",
    "ml-tbc-en.jsonl": "5e4a2f86002a0b642d3a90481bd29174a854e0d8ea663d40c0cf6726ade9efba",
    "ml-retail-de.jsonl": "80d275d95b6a5ed6e13068b60703cfc3b5b1eda03d2a255c2a552e6cef75450f",
    "ml-retail-en.jsonl": "9d8e9acc7b09f0728819fbbd9c0aa6535bcb70147b30752d4326b2964ff22ded",
    "wh-classic-deDE.jsonl": "97877f06d01fc3a1d3358b020a3d16922d82c457a13c69171b03c4c5165f07a4",
    "wh-classic-enUS.jsonl": "fef73aee63bdd61b7eb1964681b26a1538adc57595b1659709dbe79a42f2a4dc",
    "wh-retail-enUS.jsonl": "f6ea8d8944dd7eb405de965deb479b9f6d8cf6a2e642e96e464ce7452cf01afb",
}
RAW_HASHES = {
    "MultiLanguage/Database/Quests/deDE.lua": "b5d04ea17061d2acf86eb0dfef34d11e8b959aab14d68791de83ccfc43763780",
    "MultiLanguage/Database/Quests/enUS.lua": "6df300003f6b6b2b0704490e044d90dd8f1be259a3912f677b647d30ce975867",
    "MultiLanguage-tbc/Database/Quests/deDE.lua": "cb0e2736097dd1cffcd49dac0a8c7a1884c1f9af97ac7136d5766a1cd51a6143",
    "MultiLanguage-tbc/Database/Quests/enUS.lua": "f910f2faa8a5bf2333ad3a1c077b71171516e10c71697a658666057d18d1c158",
    "MultiLanguage-retail/Database/Quests/quests.lua": "adb60075fa4b0223ce2d9a77139833c2417984f401e75ce7e28f2125d12b0a58",
    "MultiLanguage-de-retail/Database/Quests/quests.lua": "b8492437d9d2cd26eb050f401c54dba0c6c982f79200fd452cab7bd9dd284ebd",
}
FIELDS = (("title", "title"), ("description", "description"), ("objective", "sourceObjective"),
          ("progress", "progress"), ("completion", "completion"))
HEADINGS = ("Ihr bekommt", "Ihr bekommt außerdem", "Bei Abschluss dieser Quest erhaltet Ihr",
            "Der folgende Zauber wird auf euch gewirkt", "Auf Euch wartet eine dieser Belohnungen",
            "You will receive", "You will also receive", "Upon completion of this quest you will gain",
            "The following spell will be cast on you")
TAIL = re.compile(r"(?:(?:" + "|".join(re.escape(h) for h in HEADINGS) + r"):\s*)+$")
UI = re.compile(r"(?:" + "|".join(re.escape(h) for h in HEADINGS) + r"):(?:\s*\n|\s*$)")
DEV = re.compile(r"(?i)temp text|new test again|do not (?:localize|use)|\[(?:ph|dnt|unused|deprecated|obsolete|old)\]|\btest(?:[ -]+\w+){0,2}[ -]+quest\d*\b")
DEV_TITLE = re.compile(r"(?i)(?:^\s*old\b|\b(?:unused|deprecated|obsolete|debug|dummy|nyi|dnt)\b|\b(?:not in use|not used|do not use)\b|[\[(<]\s*test\s*[\])>]|\[(?:ph|old)\])")
NUMERIC_TITLE = re.compile(r"^\s*(?:\d+\s*$|\d{6}\s+)")
GENDER = re.compile(r"\$[gG]([^:;]*):([^;]*);")


def source_path(flavor, locale):
    if flavor == "retail":
        folder = "MultiLanguage-de-retail" if locale == "deDE" else "MultiLanguage-retail"
        return folder + "/Database/Quests/quests.lua"
    return SPECS[flavor]["snapshot"] + "/Database/Quests/" + locale + ".lua"


def lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return quote(value)


def cleaned_source_field(raw, field):
    text = raw.get(field) or ""
    methods = []
    if field == "objective" and raw.get("description") and text.endswith(raw["description"]):
        prefix = text[:-len(raw["description"])].strip()
        if prefix:
            text = prefix
            methods.append("removed exact full description suffix")
    match = TAIL.search(text)
    if match:
        text = text[:match.start()]
        methods.append("removed only trailing empty reward headings")
    return clean(text), methods


def unresolved_control(text):
    # The shared reader resolves this exact standard grammar with UnitSex.
    # Keep alternatives in the probe so nested unknown controls are not hidden.
    probe = GENDER.sub(lambda match: match[1] + " " + match[2], text)
    return re.search(r"\$[A-Za-z0-9]", probe)


def prepare(audit):
    for name, expected in EXPORT_HASHES.items():
        assert digest(audit / "extracted" / name) == expected, "export changed: " + name
    for name, expected in RAW_HASHES.items():
        assert digest(audit / name) == expected, "pinned source changed: " + name
    baseline = {"classic": {locale: read_rows(audit / f"extracted/wh-classic-{locale}.jsonl")
                            for locale in ("deDE", "enUS")},
                "retail": {"enUS": read_rows(audit / "extracted/wh-retail-enUS.jsonl")}}
    libraries, report = {}, {}
    for flavor, spec in SPECS.items():
        originals = {locale: read_rows(audit / f"extracted/ml-{flavor}-{short}.jsonl")
                     for locale, short in (("deDE", "de"), ("enUS", "en"))}
        languages, stats = {}, {}
        for locale, rows in originals.items():
            kept, excluded, recovered = {}, [], []
            for qid, raw in sorted(rows.items()):
                title = clean(raw.get("title"))
                known_debug_record = qid == 1 and (
                    flavor == "classic" and title == 'The "Chow" Quest (123)aa'
                    or flavor == "tbc" and "world of Alexander craft" in (raw.get("description") or ""))
                if known_debug_record or DEV.search(title) or DEV_TITLE.search(title):
                    excluded.append({"id": qid, "field": "record", "reason": "developer/test/unused title"})
                    continue
                row = {"id": qid, "flavor": "source-reference", "locale": locale,
                       "source": "MultiLanguage " + spec["sourceFlavor"] + " " + spec["commits"][locale],
                       "sourceFlavor": spec["sourceFlavor"], "sourceRevision": spec["commits"][locale],
                       "sourceVersionUnverified": True, "bilingualPairVerified": False, "voiceUnavailable": True}
                for original, target in FIELDS:
                    raw_text = raw.get(original) or ""
                    if not raw_text.strip():
                        continue
                    text, methods = cleaned_source_field(raw, original)
                    recovered.extend({"id": qid, "field": original, "method": method} for method in methods)
                    reason = None
                    if not text:
                        reason = "empty after deterministic cleanup"
                    elif DEV.search(text):
                        reason = "developer/test marker"
                    elif UI.search(text):
                        reason = "ambiguous reward UI concatenation"
                    elif unresolved_control(text):
                        reason = "unresolved source control"
                    elif locale == "deDE" and original == "title" and NUMERIC_TITLE.search(text):
                        reason = "numeric/captured German title"
                    elif locale == "deDE" and original != "title" and normalized(text) == normalized(cleaned_source_field(originals["enUS"].get(qid, {}), original)[0]):
                        reason = "German field identical to English; not certified German"
                    if reason:
                        excluded.append({"id": qid, "field": original, "reason": reason})
                        continue
                    repair = SPACING_REPAIRS.get((qid, target, locale))
                    if repair and repair[0] in text:
                        text = text.replace(*repair)
                        recovered.append({"id": qid, "field": original, "method": "reviewed missing sentence space"})
                    row[target] = text
                objective = row.get("sourceObjective")
                if objective:
                    duplicate = next((field for field in ("description", "progress", "completion")
                                      if row.get(field) and normalized(objective) == normalized(row[field])), None)
                    if duplicate:
                        del row["sourceObjective"]
                        excluded.append({"id": qid, "field": "objective", "reason": "duplicates displayed " + duplicate})
                    else:
                        independent = baseline.get(flavor, {}).get(locale, {}).get(qid, {}).get("objectives")
                        if independent and normalized(independent) == normalized(objective):
                            row["objectives"] = row.pop("sourceObjective")
                            row["objectivesStatus"] = "corroborated by independent bundled same-flavor locale corpus"
                        else:
                            row["sourceObjectiveStatus"] = "unverified-source-field"
                if not any(row.get(field) for field in ("title", "description", "objectives", "sourceObjective", "progress", "completion")):
                    excluded.append({"id": qid, "field": "record", "reason": "no usable text fields"})
                    continue
                kept[qid] = row
            languages[locale] = kept
            counts = dict(collections.Counter(field for row in kept.values() for field in
                          ("title", "description", "objectives", "sourceObjective", "progress", "completion") if row.get(field)))
            stats[locale] = {"sourceRecords": len(rows), "retainedRecords": len(kept), "fields": counts,
                             "excluded": excluded, "excludedReasonCounts": dict(collections.Counter(x["reason"] for x in excluded)),
                             "deterministicRecoveries": recovered}
        libraries[spec["key"]] = languages
        report[spec["key"]] = {"label": spec["label"], "sourceFlavor": spec["sourceFlavor"],
                               "bilingualPairVerified": False, "sourceVersionUnverified": True,
                               "pairedRetainedIds": len(languages["deDE"].keys() & languages["enUS"].keys()),
                               "locales": stats}
    return libraries, report


def context_and_condition(flavor):
    if flavor == "tbc":
        return ('local version = GetBuildInfo and GetBuildInfo()\n',
                'type(version) == "string" and version:match("^2%.")')
    test = 'flavor == "retail"' if flavor == "retail" else 'flavor and flavor ~= "retail"'
    return ('local addon = WordHunterWoW_Addon\nlocal compat = addon and addon.Compat\n'
            'local flavor = compat and compat.GameFlavor and compat.GameFlavor()\n', test)


def guard(flavor):
    context, condition = context_and_condition(flavor)
    return context + 'if not (' + condition + ') then return end\n'


def write(out, libraries, report):
    names = ["ReferenceMetadata.lua"]
    meta = ["-- Generated by QuestData/Tools/import_multilanguage_references.py.",
            "-- References require explicit selection; they never merge into native quest buckets.",
            "WordHunterWoW_QuestSources = WordHunterWoW_QuestSources or {}",
            "local sources = WordHunterWoW_QuestSources"]
    for flavor, spec in SPECS.items():
        key = spec["key"]
        metadata = {"label": spec["label"], "sourceFlavor": spec["sourceFlavor"], "sourceVersionUnverified": True,
                    "bilingualPairVerified": False, "voiceUnavailable": True, "loaded": False}
        entries = [name + " = " + lua(value) for name, value in metadata.items()]
        entries.append("locales = { deDE = {}, enUS = {} }")
        locale_sources = []
        for locale, revision in spec["commits"].items():
            path = source_path(flavor, locale)
            repo = "https://github.com/rubenzantingh/" + ("MultiLanguage-de" if flavor == "retail" and locale == "deDE" else "MultiLanguage")
            locale_sources.append(locale + " = { revision = " + quote(revision) + ", repository = " + quote(repo)
                                  + ", path = " + quote(path.split("/", 1)[1]) + ", sha256 = " + quote(RAW_HASHES[path]) + " }")
        entries.append("localeSources = { " + ", ".join(locale_sources) + " }")
        context, condition = context_and_condition(flavor)
        meta.append("do\n" + context + "if " + condition + " then\nsources[" + quote(key)
                    + "] = { " + ", ".join(entries) + " }\nend\nend")
        for locale, rows in libraries[key].items():
            ordered = sorted(rows.items())
            for start in range(0, len(ordered), 250):
                name = f"References/{flavor}/{locale}_{start // 250:03d}.lua"
                path = out / name
                path.parent.mkdir(parents=True, exist_ok=True)
                prefix = ('-- Generated source references; not native quest records.\n' + guard(flavor)
                          + 'local pack = WordHunterWoW_QuestSources and WordHunterWoW_QuestSources[' + quote(key) + ']\n'
                          + 'if not pack then return end\npack.loaded = true\nlocal quests = pack.locales.' + locale + '\n')
                lines = [prefix]
                for qid, row in ordered[start:start + 250]:
                    values = [field + " = " + lua(value) for field, value in row.items()]
                    lines.append("quests[" + str(qid) + "] = { " + ", ".join(values) + " }")
                path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
                names.append(name)
        report[key]["files"] = [name for name in names if name.startswith("References/" + flavor + "/")]
    (out / names[0]).write_bytes(("\n".join(meta) + "\n").encode("utf-8"))
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Optional full exclusion/recovery artifact outside addon")
    parser.add_argument("--corpus", type=Path, help="Optional normalized accepted text JSONL outside addon")
    args = parser.parse_args()
    libraries, report = prepare(args.audit)
    manifest_path = args.out / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if not name.startswith("References/") and name != "ReferenceMetadata.lua":
            assert digest(args.out / name) == expected, "existing native/default pack changed: " + name
    names = write(args.out, libraries, report)
    # Remove only untouched stale chunks previously generated by this importer.
    # This keeps filesystem-discovered bundle manifests from resurrecting excluded data.
    for name in set(manifest.get("referenceSources", {}).get("files", [])) - set(names):
        target = (args.out / name).resolve()
        assert name.startswith("References/") and target.suffix == ".lua"
        assert target.is_relative_to((args.out / "References").resolve()), "stale chunk escaped destination"
        if target.exists():
            assert digest(target) == manifest["files"][name], "stale generated chunk was edited"
            target.unlink()
        manifest["files"].pop(name, None)
    manifest["files"].update({name: digest(args.out / name) for name in names})
    manifest["referenceSources"] = {
        "files": names, "inputExportsSha256": EXPORT_HASHES, "rawSourceSha256": RAW_HASHES,
        "policy": "Explicit source selection only. Client guards retain Classic master on non-Retail, Retail only on Retail, TBC only on version 2.x. Native catalogs and accepted compatibility overlays unchanged.",
        "objectivePolicy": "Independent same-flavor/same-locale corroboration required for objectives; otherwise sourceObjective is explicitly unverified. Exact phase duplicates are omitted because their text remains in the corresponding displayed phase.",
        "normalization": "Pinned decoded literals; HTML/scalar placeholders and NBSP normalization. Standard $gMale:Female; gender macros stay literal for the shared reader; nested unknown controls remain excluded. Deterministic empty reward-heading/exact-description-tail cleanup only. Unknown controls and uncertain reward concatenations are excluded per field.",
        "bilingualPairVerified": False, "sourceVersionUnverified": True,
        "permission": "Author permission reported by project owner on 2026-10-05; upstream rights and source attribution preserved.",
        "sources": report,
    }
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes((json.dumps(manifest["referenceSources"], ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if args.corpus:
        args.corpus.parent.mkdir(parents=True, exist_ok=True)
        with args.corpus.open("w", encoding="utf-8", newline="\n") as corpus:
            for key, languages in libraries.items():
                for locale, rows in languages.items():
                    for qid, row in rows.items():
                        for field in ("title", "description", "objectives", "sourceObjective", "progress", "completion"):
                            if row.get(field):
                                corpus.write(json.dumps({"locale": locale, "id": qid, "kind": "quest",
                                             "sourceFlavor": key, "text": row[field], "category": field}, ensure_ascii=False) + "\n")
    print(json.dumps({key: {"pairedRetainedIds": info["pairedRetainedIds"], "locales": {
        locale: {k: v for k, v in stats.items() if k not in ("excluded", "deterministicRecoveries")}
        for locale, stats in info["locales"].items()}} for key, info in report.items()}))


if __name__ == "__main__":
    main()
