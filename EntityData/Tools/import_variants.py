"""Import pinned, client-specific entity references without changing Classic files."""
from pathlib import Path
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import re
import subprocess
import urllib.request

import import_entities as base

ROOT = base.ROOT
INPUTS = Path(__file__).resolve().parents[4] / "development-inputs/multilanguage-next-20261006/entities"
EDITIONS = {
    "tbc": [("MultiLanguage", "tbc-classic", "fe999319f2c9c4c3cdd1bc60c8ae711c079b175f", ["deDE", "enUS"])],
    "retail": [("MultiLanguage", "retail", "fb8e7e9117b5c99347d05ec8a30b0644fbef4fb8", ["enUS"]), ("MultiLanguage-de", "retail", "a54af98d3013271c6f2cac8c5c00bbf4d74185bd", ["deDE"])],
    "wrath": [("MultiLanguage", "wotlk", "108ede6c1fccfff2d41f291c49a032759a8a76c8", ["enUS"]), ("MultiLanguage-de", "historical-last-wotlk", "a0a5e66931a7f13f06e4f73d1dd472215c5da5a9", ["deDE"])],
    "cata": [("MultiLanguage", "cata", "cc638509ca3347e4c22bf6187dac4c2443b9057d", ["enUS"]), ("MultiLanguage-de", "master", "868743d847392a43bf3b353501432d64db8b8820", ["deDE"])],
    "mop-classic": [("MultiLanguage", "mop-classic", "ff01f8cbdd3bd8fd7644fb785dcf1e6f76a28c37", ["enUS"]), ("MultiLanguage-de", "mop-classic", "a9e7ba2d7b8654481abbd70f7190b341346c68eb", ["deDE"])],
    "forever": [("MultiLanguage", "forever", "87d8e5f4c904291c24296205df97c9bc96aa6943", ["deDE", "enUS"])],
}
LABELS = {"tbc": "TBC", "retail": "Retail", "wrath": "Wrath", "cata": "Cata", "mop-classic": "MoP", "forever": "Forever"}
GLOBALS = {"item": "MultiLanguageItemData", "npc": "MultiLanguageNpcData", "spell": "MultiLanguageSpellData"}
PERMISSION = "Author permission reported by project owner on 2026-10-05; upstream LICENSE remains All rights reserved."
VARIANT_DEVELOPER = re.compile(r"\bOnly GM can see|\bGM[- ]Only\b|^zzOLD\b", re.I)


def developer_reason(name, kind):
    return base.developer_reason(name, kind) or ("explicit GM-only or retired developer label" if VARIANT_DEVELOPER.search(name) else None)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def json_write(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def raw_url(repo, pin, path):
    return f"https://raw.githubusercontent.com/rubenzantingh/{repo}/{pin}/{path}"


def fetch_catalog(inputs):
    """TOC membership is authoritative; keep untranslated locales and stray files out."""
    snapshots, files, excluded = [], [], []
    previous_path = ROOT / "Source/Variants/source-catalog.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    cached_blobs = {row["gitBlob"]: row for row in previous.get("files", [])}
    for edition, revisions in EDITIONS.items():
        for repo, branch, pin, locales in revisions:
            tree = json.loads(subprocess.check_output(["gh", "api", f"repos/rubenzantingh/{repo}/git/trees/{pin}?recursive=1"], encoding="utf-8"))
            assert not tree.get("truncated"), "An incomplete upstream tree cannot establish coverage."
            members = {row["path"]: row for row in tree["tree"] if row["type"] == "blob"}
            toc_path = "MultiLanguage_DE.toc" if repo.endswith("-de") else "MultiLanguage.toc"
            with urllib.request.urlopen(raw_url(repo, pin, toc_path)) as stream:
                toc = stream.read()
            load_order = [line.strip().replace("\\", "/") for line in toc.decode("utf-8-sig").splitlines() if line.strip().startswith("Database/")]
            snapshot = {"edition": edition, "repo": f"https://github.com/rubenzantingh/{repo}", "repository": repo, "branch": branch, "commit": pin, "locales": locales, "interface": re.search(r"## Interface:\s*([^\r\n]+)", toc.decode("utf-8-sig")).group(1), "toc": toc_path, "treeSha": tree["sha"]}
            snapshots.append(snapshot)
            selected = []
            for path in load_order:
                kind = next((kind for kind, (folder, _) in base.KINDS.items() if path.startswith("Database/" + folder + "/") or path == "Database/" + folder.lower() + ".lua"), None)
                if not kind:
                    continue
                if re.search(r"/(?:[a-z]{2}[A-Z]{2})\.lua$", path) and Path(path).stem not in locales:
                    continue
                selected.append(path)
                row = members[path]
                locale = Path(path).stem if Path(path).stem in locales else (locales[0] if len(locales) == 1 else None)
                # The tiny table initializers are retained as provenance, not executed.
                role = "bootstrap" if row["size"] < 200 else "payload"
                files.append({"edition": edition, "repository": repo, "branch": branch, "commit": pin, "path": path, "kind": kind, "locale": locale, "role": role, "gitBlob": row["sha"], "rawBytes": row["size"]})
            for path in sorted(members):
                if path.startswith("Database/") and path.endswith(".lua") and path not in load_order and any(path.startswith("Database/" + folder + "/") for folder, _ in base.KINDS.values()):
                    excluded.append({"edition": edition, "repository": repo, "commit": pin, "path": path, "gitBlob": members[path]["sha"], "reason": "Not loaded by the pinned upstream TOC; no inferred client or locale."})
            for path, role in [(toc_path, "toc")] + ([("LICENSE", "license")] if "LICENSE" in members else []):
                row = members[path]
                files.append({"edition": edition, "repository": repo, "branch": branch, "commit": pin, "path": path, "role": role, "gitBlob": row["sha"], "rawBytes": row["size"]})
            print(f"catalog {edition} {repo}: {len(selected)} entity files", flush=True)
    # One download per immutable Git blob, even when many edition loaders are identical.
    grouped = {}
    for row in files:
        grouped.setdefault(row["gitBlob"], []).append(row)
    def download(rows):
        row = rows[0]
        cached = cached_blobs.get(row["gitBlob"])
        archive = ROOT.parent / cached["archive"] if cached else None
        if archive and archive.exists():
            compressed = archive.read_bytes()
            assert base.sha(compressed) == cached["archiveSha256"], "Cached archive hash mismatch."
            raw = gzip.decompress(compressed)
            assert base.sha(raw) == cached["rawSha256"], "Cached raw source hash mismatch."
        else:
            with urllib.request.urlopen(raw_url(row["repository"], row["commit"], row["path"])) as stream:
                raw = stream.read()
        git_hash = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert git_hash == row["gitBlob"] and len(raw) == row["rawBytes"], "Pinned Git blob/size mismatch."
        digest, compressed = base.sha(raw), base.deterministic_gzip(raw)
        external = inputs / "Source" / (digest + ".gz")
        archive = ROOT / "Source/Variants" / (digest + ".gz")
        write(external, compressed)
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            try:
                os.link(external, archive)
            except OSError:
                write(archive, compressed)
        assert archive.read_bytes() == compressed
        for item in rows:
            item.update(url=f"https://github.com/rubenzantingh/{item['repository']}/blob/{item['commit']}/{item['path']}", rawSha256=digest, archive="EntityData/Source/Variants/" + archive.name, archiveSha256=base.sha(compressed), archiveBytes=len(compressed))
        return len(rows), len(raw)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for count, size in pool.map(download, grouped.values()):
            print(f"preserved {count} source references / {size} bytes", flush=True)
    catalog = {"schemaVersion": 1, "permissionBasis": PERMISSION, "license": "All rights reserved; no open-source grant is inferred.", "snapshots": snapshots, "files": files, "excludedSourceFiles": excluded, "unavailableSources": []}
    json_write(inputs / "source-catalog.json", catalog)
    json_write(ROOT / "Source/Variants/source-catalog.json", catalog)
    return catalog


def read_payload(raw, kind, locale, lua_command):
    """Use Lua itself to decode source literals, in an isolated build-only environment."""
    reader = base.LUA_READER.replace("local env,addon = {}, {itemData={}, npcData={}, spellData={}}", "local addon = {itemData={}, npcData={}, spellData={}}\nlocal env = {MultiLanguageItemData={de={},en={}}, MultiLanguageNpcData={de={},en={}}, MultiLanguageSpellData={de={},en={}}}")
    _, table = base.KINDS[kind]
    short = base.LOCALES[locale]
    reader = reader.replace("print(emit(addon))", f"print(emit(addon.{table}[{base.quote(short)}] or env.{GLOBALS[kind]}[{base.quote(short)}]))")
    script = "local SOURCE_TEXT = " + base.quote(raw.decode("utf-8-sig")) + "\n" + reader
    result = subprocess.run(lua_command + ["-"], input=script, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    rows = json.loads(result.stdout)
    assert all(key.isdecimal() and isinstance(row, dict) for key, row in rows.items()), "Entity source must contain numeric IDs and records."
    return rows


def guard(edition):
    prefix = "local addon = WordHunterWoW_Addon\nlocal compat = addon and addon.Compat\nif not (compat and compat.GameFlavor) then return end\nlocal flavor = compat.GameFlavor()\n"
    if edition in ("retail", "forever"):
        return prefix + f"if flavor ~= {base.quote(edition)} then return end\n"
    major = {"tbc": "2", "wrath": "3", "cata": "4", "mop-classic": "5"}[edition]
    return prefix + f"local version = GetBuildInfo and GetBuildInfo()\nif not ((flavor == \"classic\" or flavor == \"sod\" or flavor == \"forever\") and type(version) == \"string\" and version:match(\"^{major}%.%d+%.%d+$\")) then return end\n"


def build(catalog, lua_command, corpus_path):
    manifest_path = ROOT / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Preserve the original Classic metadata/chunks and their established counts.
    classic_files = {path: row for path, row in manifest["generatedFiles"].items() if not path.startswith("EntityData/Variants/")}
    for path, row in classic_files.items():
        assert base.sha((ROOT.parent / path).read_bytes()) == row["sha256"], f"Classic generated file changed: {path}"
    classic_order = [path for path in manifest["runtime_load_order"] if not path.startswith("EntityData/Variants/")]
    manifest["generatedFiles"], manifest["runtime_load_order"] = dict(classic_files), list(classic_order)
    manifest["sources"], manifest["unavailableSources"] = {}, catalog["unavailableSources"]
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_rows, by_locale = 0, {locale: 0 for locale in base.LOCALES}
    with corpus_path.with_name(corpus_path.name + ".tmp").open("w", encoding="utf-8", newline="\n") as corpus:
        for edition in EDITIONS:
            source_key = "multilanguage-" + edition
            files = [row for row in catalog["files"] if row["edition"] == edition]
            snapshots = [row for row in catalog["snapshots"] if row["edition"] == edition]
            source = {"schemaVersion": 1, "sourceKey": source_key, "sourceLabel": "MultiLanguage " + LABELS[edition] + " reference", "viewLabel": "ML " + LABELS[edition], "referenceOnly": True, "permissionBasis": PERMISSION, "provenance": {"edition": edition, "locales": {locale: {key: snapshot[key] for key in ("repo", "branch", "commit", "interface")} for snapshot in snapshots for locale in snapshot["locales"]}}, "sourceFiles": files, "counts": {}, "normalization": dict(manifest["normalization"], changedFieldValues=0, recordsWithUnresolvedValues=0), "quality": {key: value for key, value in manifest["quality"].items() if key not in ("recordExclusions", "fieldExclusions")}, "runtime_load_order": [], "generatedFiles": {}}
            source["quality"].update(recordExclusions=[], fieldExclusions=[], shardOverlapPolicy="Pinned TOC order, later source assignment wins; overlapping IDs and changed values are recorded per source file.", variantDeveloperPolicy="Additionally omit explicit GM-only and zzOLD retired developer labels; preserve ordinary training dummies and legitimate Test of names.")
            for kind in base.KINDS:
                raw_rows = {locale: {} for locale in base.LOCALES}
                for row in files:
                    if row["role"] != "payload" or row["kind"] != kind:
                        continue
                    archive = ROOT.parent / row["archive"]
                    compressed = archive.read_bytes()
                    assert base.sha(compressed) == row["archiveSha256"]
                    raw = gzip.decompress(compressed)
                    assert base.sha(raw) == row["rawSha256"]
                    rows = read_payload(raw, kind, row["locale"], lua_command)
                    row["sourceRecords"] = len(rows)
                    current = raw_rows[row["locale"]]
                    overlap = current.keys() & rows.keys()
                    row["overlappingIDs"] = sorted(int(key) for key in overlap)
                    row["changedOverlappingIDs"] = sorted(int(key) for key in overlap if current[key] != rows[key])
                    current.update(rows)
                excluded = {}
                for locale, rows in raw_rows.items():
                    for key, row in rows.items():
                        reason = developer_reason(base.clean(row.get("name"), locale)[0], kind)
                        if reason:
                            excluded[key] = reason
                for key, reason in sorted(excluded.items(), key=lambda pair: int(pair[0])):
                    source["quality"]["recordExclusions"].append({"kind": kind, "id": int(key), "reason": reason, "sourceNames": {locale: rows[key].get("name") for locale, rows in raw_rows.items() if key in rows}})
                clean_rows = {locale: {} for locale in base.LOCALES}
                source["counts"][kind] = {}
                for locale, rows in raw_rows.items():
                    for key, row in sorted(rows.items(), key=lambda pair: int(pair[0])):
                        if key in excluded:
                            continue
                        name, unresolved = base.clean(row.get("name"), locale)
                        if not name:
                            continue
                        record = {"name": name}
                        for raw_field, field in [("additional_info", "text"), ("subname", "role")]:
                            if not row.get(raw_field):
                                continue
                            text, field_unresolved = base.clean(row[raw_field], locale)
                            if locale == "deDE" and text:
                                english = base.clean(raw_rows["enUS"].get(key, {}).get(raw_field), "enUS")[0]
                                exclusion = base.english_prose(text, english)
                                if exclusion:
                                    source["quality"]["fieldExclusions"].append({"kind": kind, "id": int(key), "locale": locale, "field": field, **exclusion})
                                    continue
                            unresolved = unresolved or field_unresolved
                            if text:
                                record[field] = text
                            source["normalization"]["changedFieldValues"] += text != row[raw_field]
                        source["normalization"]["changedFieldValues"] += name != row.get("name")
                        if unresolved:
                            record["unresolvedValues"] = True
                            source["normalization"]["recordsWithUnresolvedValues"] += 1
                        clean_rows[locale][int(key)] = record
                        for field in ("name", "text", "role"):
                            if record.get(field):
                                corpus.write(json.dumps({"locale": locale, "id": int(key), "kind": kind, "sourceFlavor": source_key, "category": field, "text": record[field]}, ensure_ascii=False, separators=(",", ":")) + "\n")
                                corpus_rows += 1
                                by_locale[locale] += 1
                    records = clean_rows[locale]
                    excluded_count = len(rows.keys() & excluded.keys())
                    source["counts"][kind][locale] = {"records": len(records), "text": sum(bool(row.get("text")) for row in records.values()), "role": sum(bool(row.get("role")) for row in records.values()), "unresolvedValues": sum(bool(row.get("unresolvedValues")) for row in records.values()), "sourceRecords": len(rows), "excludedDeveloperRecords": excluded_count, "omittedEmptyNames": len(rows) - len(records) - excluded_count}
                    items = list(records.items())
                    for index, start in enumerate(range(0, len(items), base.CHUNK)):
                        path = ROOT / "Variants" / edition / "Data" / kind / (locale + "_%03d.lua" % index)
                        header = "-- Generated static reference; see EntityData/source-manifest.json.\nlocal ref = WordHunterWoW_EntityDataBySource and WordHunterWoW_EntityDataBySource[" + base.quote(source_key) + "]\nif not ref then return end\nlocal entries = ref.kinds[" + base.quote(kind) + "][" + base.quote(locale) + "]\n"
                        data = (header + "".join("entries[%d] = %s\n" % (key, base.literal(record)) for key, record in items[start:start + base.CHUNK])).encode("utf-8")
                        write(path, data)
                        game_path = "EntityData/" + path.relative_to(ROOT).as_posix()
                        source["runtime_load_order"].append(game_path)
                        source["generatedFiles"][game_path] = {"sha256": base.sha(data), "bytes": len(data)}
                de, en = set(clean_rows["deDE"]), set(clean_rows["enUS"])
                source["counts"][kind]["coverage"] = {"pairedNames": len(de & en), "deOnly": len(de - en), "enOnly": len(en - de), "pairedText": sum(bool(clean_rows["deDE"][key].get("text")) and bool(clean_rows["enUS"][key].get("text")) for key in de & en), "pairedRoles": sum(bool(clean_rows["deDE"][key].get("role")) and bool(clean_rows["enUS"][key].get("role")) for key in de & en)}
                print(f"built {edition}/{kind}: DE {len(de)}, EN {len(en)}", flush=True)
            metadata_path = ROOT / "Variants" / edition / "Metadata.lua"
            metadata = "-- Client-specific static reference. Native gameplay tables remain untouched.\n" + guard(edition) + "WordHunterWoW_EntityDataBySource = WordHunterWoW_EntityDataBySource or {}\nlocal ref = " + base.literal({key: source[key] for key in ("schemaVersion", "sourceLabel", "viewLabel", "referenceOnly", "provenance", "counts")}) + "\nref.kinds = { item = { deDE = {}, enUS = {} }, npc = { deDE = {}, enUS = {} }, spell = { deDE = {}, enUS = {} } }\nWordHunterWoW_EntityDataBySource[" + base.quote(source_key) + "] = ref\n"
            data = metadata.encode("utf-8")
            write(metadata_path, data)
            game_path = "EntityData/" + metadata_path.relative_to(ROOT).as_posix()
            source["runtime_load_order"].insert(0, game_path)
            source["generatedFiles"][game_path] = {"sha256": base.sha(data), "bytes": len(data)}
            manifest["sources"][source_key] = source
            manifest["runtime_load_order"].extend(source["runtime_load_order"])
            manifest["generatedFiles"].update(source["generatedFiles"])
    os.replace(corpus_path.with_name(corpus_path.name + ".tmp"), corpus_path)
    corpus_data = corpus_path.read_bytes()
    manifest["variantNormalizedCorpus"] = {"file": corpus_path.name, "sha256": base.sha(corpus_data), "bytes": len(corpus_data), "rows": corpus_rows, "rowsByLocale": by_locale}
    manifest["excludedSourceFiles"] = catalog["excludedSourceFiles"]
    manifest["variantSourceCatalog"] = "EntityData/Source/Variants/source-catalog.json"
    allowed = set(manifest["generatedFiles"])
    variant_root = ROOT / "Variants"
    for path in variant_root.rglob("*.lua"):
        relative = path.relative_to(variant_root)
        assert relative.parts[0] in EDITIONS and (path.name == "Metadata.lua" or re.fullmatch(r"(?:deDE|enUS)_\d{3}\.lua", path.name)), "Unexpected variant file; refuse cleanup."
        if "EntityData/" + path.relative_to(ROOT).as_posix() not in allowed:
            path.unlink()
    json_write(manifest_path, manifest)
    write(ROOT / "tests/load-order.lua", ("return {\n" + "".join("  " + base.quote(path) + ",\n" for path in manifest["runtime_load_order"]) + "}\n").encode("utf-8"))
    json_write(corpus_path.parent / "import-report.json", {"passed": True, "sources": {key: source["counts"] for key, source in manifest["sources"].items()}, "corpus": manifest["variantNormalizedCorpus"], "runtimeFiles": len(manifest["runtime_load_order"]), "classicFilesPreserved": len(classic_files), "newTranscodes": 0})
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch the immutable pinned inputs using GitHub API plus raw blobs.")
    parser.add_argument("--inputs", type=Path, default=INPUTS)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--lua-command", nargs=argparse.REMAINDER, default=["lua"], help="Last option: build-only Lua command, e.g. wsl -d Debian -e lua5.1")
    args = parser.parse_args()
    base.checks()
    catalog = fetch_catalog(args.inputs) if args.fetch else json.loads((ROOT / "Source/Variants/source-catalog.json").read_text(encoding="utf-8"))
    result = build(catalog, args.lua_command, args.corpus or args.inputs / "normalized-entity-corpus.jsonl")
    print(json.dumps({"passed": True, "sourceKeys": list(result["sources"]), "runtimeFiles": len(result["runtime_load_order"]), "corpus": result["variantNormalizedCorpus"]}, ensure_ascii=False))
