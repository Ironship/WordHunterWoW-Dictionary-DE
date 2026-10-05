"""Add reviewed, bilingual MultiLanguage passages to the existing quest pack.

The 2026-10-05 audit exports are immutable input evidence, not live game caches.
This does not translate vocabulary, fetch new quest IDs, or edit SavedVariables.
"""
import argparse
import collections
import hashlib
import html
import json
from pathlib import Path
import re

from build_quest_data import quote

COMMIT = "c51dc2e5141f070f5b92de190521d79e8dccaeab"
SOURCE = "MultiLanguage Classic " + COMMIT
INPUTS = {
    "candidates/classic-dialogue.jsonl": "673c57b6659a56a33404e46c045d947e331f4b148dd66b800a11d29eea6f1ede",
    "candidates/forever-dialogue.jsonl": "c0a6ac257804e5e23e94374d024b232d4bed5a5b0c740324213141c5fc7dd4ef",
    "gap-sceptic-clean-descriptions.json": "f2a4eb9417a85cdc3cd19a53f45af1eea7ddc2c2062a9289fae820da5427791c",
    "gap-sceptic-objective-candidates.json": "09543caac94647224f481bef009f2a2daacfa868205ff5f39e5d3a1d31862b67",
    "extracted/wh-classic-deDE.jsonl": "97877f06d01fc3a1d3358b020a3d16922d82c457a13c69171b03c4c5165f07a4",
    "extracted/wh-classic-enUS.jsonl": "fef73aee63bdd61b7eb1964681b26a1538adc57595b1659709dbe79a42f2a4dc",
    "extracted/wh-forever-deDE.jsonl": "6c1aa43b717cf454ea6b71e44181e7566044a059e730373b191c2c6accb38709",
    "extracted/wh-forever-enUS.jsonl": "0ac1c859a66ba699af4a028bbd567b85774bae0bce835f896ba9cbd0b2ea50e3",
    "extracted/ml-classic-de.jsonl": "c13daaccf5904609dba1a80a4dee1b7202ba98aee12cd48e8ed65c5d1a8cfc41",
    "extracted/ml-classic-en.jsonl": "5881f384c7873b9c204db449b5f9b884fe5a85a41cda9c62226ff27f53a45638",
}
SOURCE_HASHES = {
    "Database/Quests/deDE.lua": "b5d04ea17061d2acf86eb0dfef34d11e8b959aab14d68791de83ccfc43763780",
    "Database/Quests/enUS.lua": "6df300003f6b6b2b0704490e044d90dd8f1be259a3912f677b647d30ce975867",
}
REVIEW_IDS = {7221, 7222, 7704, 8290, 8295, 8856, 8869}
SPACING_REPAIRS = {
    (8517, "completion", "deDE"): ("erfährt.Gebt", "erfährt. Gebt"),
    (9002, "completion", "deDE"): ("{name}.Ich", "{name}. Ich"),
}
FIELDS = ("description", "objectives", "progress", "completion")
BAD = re.compile(r"(?i)temp text|new test again|do not localize|\[ph\]|\btest quest\b")
UI = re.compile(r"(?:Ihr bekommt(?: außerdem)?|You will receive|Bei Abschluss dieser Quest erhaltet Ihr|Upon completion of this quest you will gain|Der folgende Zauber wird auf euch gewirkt|Auf Euch wartet eine dieser Belohnungen):(?:\s*\n|\s*$)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    text = html.unescape(str(text or "").replace("$B", "\n").replace("$b", "\n"))
    for token, names, macro in (("name", "Name|name", "nN"),
                                ("class", "Klasse|klasse|Class|class", "cC"),
                                ("race", "Rasse|rasse|Volk|volk|Race|race", "rR")):
        text = re.sub(r"<(?:" + names + r")>", "{" + token + "}", text)
        text = re.sub(r"\$[" + macro + "]", "{" + token + "}", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").replace("\u202f", " ").strip()


def normalized(text):
    text = clean(text).casefold()
    # Compare equivalent Blizzard/source gender notation; displayed alternatives stay intact.
    text = re.sub(r"\$g([^:;]+):([^;]+);", lambda m: "<" + m[1] + "/" + m[2] + ">", text)
    return re.sub(r"\s+", " ", text)


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len({row["id"] for row in rows}), path
    return {row["id"]: row for row in rows}


def opening_matches(source, current):
    matches = []
    for src, dst in (("description", "description"), ("objective", "objectives")):
        if source.get(src) and current.get(dst):
            matches.append(normalized(source[src]) == normalized(current[dst]))
    return bool(matches) and all(matches)


def select(audit):
    for name, expected in INPUTS.items():
        assert digest(audit / name) == expected, "audit input changed: " + name
    for name, expected in SOURCE_HASHES.items():
        assert digest(audit / "MultiLanguage" / name) == expected, "source changed: " + name
    source = {locale: read_rows(audit / f"extracted/ml-classic-{short}.jsonl")
              for locale, short in (("deDE", "de"), ("enUS", "en"))}
    selected, counts = {}, {}
    for flavor in ("classic", "forever"):
        current = {locale: read_rows(audit / f"extracted/wh-{flavor}-{locale}.jsonl")
                   for locale in ("deDE", "enUS")}
        accepted, dialogue_ids = {}, []
        for qid, row in read_rows(audit / f"candidates/{flavor}-dialogue.jsonl").items():
            assert row["source_commit"] == COMMIT and row["target_flavor"] == flavor
            if not row["opening_matches_both_languages"] or any(f["flags"] for f in row["fields"].values()):
                continue
            assert all(qid in current[locale] and qid in source[locale] and
                       opening_matches(source[locale][qid], current[locale][qid])
                       for locale in current), (flavor, qid)
            payload = {locale: {} for locale in current}
            for field, value in row["fields"].items():
                assert field in ("progress", "completion")
                # A DE-only fragment cannot be shown as a bilingual passage.
                if not value["deDE"] or not value["enUS"]:
                    continue
                for locale in current:
                    raw = source[locale][qid][field]
                    assert raw == value["raw_" + locale] and clean(raw) == clean(value[locale])
                    assert not BAD.search(raw) and not UI.search(raw), (qid, locale, field)
                    assert not current[locale][qid].get(field), "existing passage must win"
                    text = clean(raw)
                    repair = SPACING_REPAIRS.get((qid, field, locale))
                    if repair:
                        assert text.count(repair[0]) == 1, "reviewed spacing repair changed"
                        text = text.replace(*repair)
                    payload[locale][field] = text
            assert payload["deDE"] and set(payload["deDE"]) == set(payload["enUS"])
            accepted[qid] = payload
            dialogue_ids.append(qid)
        for field, name in (("description", "gap-sceptic-clean-descriptions.json"),
                            ("objectives", "gap-sceptic-objective-candidates.json")):
            reviewed = json.loads((audit / name).read_text(encoding="utf-8"))
            assert {row["id"] for row in reviewed} == REVIEW_IDS
            for row in reviewed:
                qid = row["id"]
                assert row["source_commit"] == COMMIT and qid in current["deDE"]
                assert not current["deDE"][qid].get(field), "opening fill must not replace text"
                raw = source["deDE"][qid]["objective" if field == "objectives" else field]
                assert row["raw_deDE"] == raw
                assert digest_text(row["clean_deDE"]) == row["clean_deDE_utf8_sha256"]
                if field == "description":
                    assert raw == row["clean_deDE"] + row["removed_suffix"]
                    assert normalized(current["enUS"][qid][field]) == normalized(row["clean_enUS"])
                else:
                    assert raw == row["clean_deDE"] + row["removed_exact_source_description_suffix"]
                    assert normalized(current["enUS"][qid][field]) == normalized(row["existing_enUS_objectives"])
                text = clean(row["clean_deDE"])
                assert text and not BAD.search(text) and not UI.search(text)
                accepted.setdefault(qid, {"deDE": {}, "enUS": {}})["deDE"][field] = text
        field_counts = {locale: dict(collections.Counter(field for row in accepted.values()
                       for field in row[locale])) for locale in current}
        assert len(dialogue_ids) == (2707 if flavor == "classic" else 2706)
        assert field_counts["deDE"] == {"progress": 1873 if flavor == "classic" else 1872,
                                        "completion": len(dialogue_ids), "description": 7, "objectives": 7}
        selected[flavor] = accepted
        counts[flavor] = {"dialogueRecords": len(dialogue_ids), "dialogueIds": sorted(dialogue_ids),
                           "filledFields": field_counts, "openingFillIds": sorted(REVIEW_IDS),
                           "recordCountUnchanged": len(current["deDE"])}
    assert set(selected["classic"]) - set(selected["forever"]) == {2541}
    assert not (set(selected["forever"]) - set(selected["classic"]))
    return selected, counts


def digest_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_overlay(out, selected):
    names = []
    root = out / "MultiLanguage"
    root.mkdir(exist_ok=True)
    prefix = '''-- Generated by QuestData/Tools/import_multilanguage_quests.py.
-- Known IDs only; Classic-source passages are compatibility fallbacks on Forever.
local source = "''' + SOURCE + '''"
local data = WordHunterWoW_QuestDataByFlavor
local function apply(id, targets, passages)
    for _, flavor in ipairs(targets) do
        local languages = data and data[flavor]
        for locale, fields in pairs(passages) do
            local record = languages and languages[locale] and languages[locale][id]
            if record then
                for field, text in pairs(fields) do
                    if not record[field] or record[field] == "" then
                        record[field] = text
                        record[field .. "Source"] = source
                        record[field .. "SourceFlavor"] = "classic"
                    end
                end
            end
        end
    end
end
'''
    ids = sorted(set(selected["classic"]) | set(selected["forever"]))
    for start in range(0, len(ids), 250):
        name = f"MultiLanguage/{start // 250:03d}.lua"
        lines = [prefix]
        for qid in ids[start:start + 250]:
            targets = [flavor for flavor in ("classic", "forever") if qid in selected[flavor]]
            payload = selected[targets[0]][qid]
            assert all(selected[flavor][qid] == payload for flavor in targets)
            languages = []
            for locale in ("deDE", "enUS"):
                fields = [field + " = " + quote(payload[locale][field])
                          for field in FIELDS if field in payload[locale]]
                if fields:
                    languages.append(locale + " = { " + ", ".join(fields) + " }")
            lines.append("apply(" + str(qid) + ", { " + ", ".join(quote(t) for t in targets)
                         + " }, { " + ", ".join(languages) + " })")
        (out / name).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        names.append(name)
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Existing Dictionary-DE/QuestData")
    parser.add_argument("--selection", type=Path, help="Optional review artifact outside addon")
    args = parser.parse_args()
    selected, counts = select(args.audit)
    manifest_path = args.out / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if not name.startswith("MultiLanguage/"):
            assert digest(args.out / name) == expected, "base pack changed: " + name
    names = write_overlay(args.out, selected)
    manifest["files"].update({name: digest(args.out / name) for name in names})
    manifest["multilanguage"] = {
        "repository": "https://github.com/rubenzantingh/MultiLanguage",
        "author": "Ruben Zantingh", "commit": COMMIT, "sourceFilesSha256": SOURCE_HASHES,
        "permission": "User reported author permission on 2026-10-05.",
        "inputArtifactsSha256": INPUTS, "counts": counts,
        "policy": "Existing IDs and nonempty fields win. Both-language opening match and unflagged bilingual dialogue only; seven reviewed DE opening fills. No source-only IDs or Retail records.",
        "liveVersionCertified": False, "foreverSource": "Explicit Classic compatibility fallback",
        "normalization": "Decode HTML; normalize paragraphs, NBSP/narrow NBSP and scalar name/class/race placeholders; preserve emotes and gender alternatives. Compare equivalent $gMale:Female; and <Male/Female> without rewriting displayed alternatives.",
        "omittedUnpairedProgressIds": [245, 1025, 7622], "files": names,
        "reviewedDisplaySpacingRepairs": [{"id": qid, "field": field, "locale": locale,
                                            "before": before, "after": after}
                                           for (qid, field, locale), (before, after) in SPACING_REPAIRS.items()],
    }
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for suffix in ("Mainline", "Vanilla"):
        toc = args.out.parent / f"WordHunterWoW-Dictionary-DE_{suffix}.toc"
        lines = [line for line in toc.read_text(encoding="utf-8").splitlines()
                 if not line.startswith("QuestData/MultiLanguage/")]
        at = lines.index("QuestData/Loader.lua")
        lines[at:at] = ["QuestData/" + name for name in names]
        toc.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    if args.selection:
        args.selection.parent.mkdir(parents=True, exist_ok=True)
        args.selection.write_bytes((json.dumps(selected, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"counts": {flavor: {k: v for k, v in info.items() if not k.endswith("Ids")}
                                  for flavor, info in counts.items()}, "files": names}))


if __name__ == "__main__":
    main()
