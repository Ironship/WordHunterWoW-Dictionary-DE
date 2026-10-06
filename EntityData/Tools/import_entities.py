"""Build an explicitly labeled static reference pack; never alter native data."""
from pathlib import Path
import argparse
import gzip
import hashlib
import html
import io
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PIN = "c51dc2e5141f070f5b92de190521d79e8dccaeab"
SOURCE_KEY = "multilanguage-classic"
REPO = "https://github.com/rubenzantingh/MultiLanguage"
KINDS = {"item": ("Items", "itemData"), "npc": ("Npcs", "npcData"), "spell": ("Spells", "spellData")}
LOCALES = {"deDE": "de", "enUS": "en"}
CHUNK = 1000
DEVELOPER_MARKERS = [
    ("QA prefix", re.compile(r"^QA(?:[A-Z0-9]|[ _-]|$)")),
    ("DND/DNT marker", re.compile(r"(?:\(|\[)(?:DND|DNT)(?:\)|\])|^(?:DND|DNT)(?:\s|[-_]|$)",re.I)),
    ("NPC equipment marker", re.compile(r"^Monster\s*-",re.I)),
    ("seasonal internal prefix", re.compile(r"^S\d{2}(?:[ _-]|Tuning)",re.I)),
    ("explicit developer status", re.compile(r"\b(?:debug|tuning|developer|deprecated|obsolete|unused|placeholder)\b",re.I)),
]
GERMAN_MARKERS = set("der die das den dem des ein eine einer einen einem eines und oder aber nicht mit von zu zur zum für auf aus im in ist sind wird werden ihr eure euren eurer euer euch erhöht verringert verursacht benutzen anlegen wirken benötigt reichweite sofort sek schaden heilt mana rüstung haltbarkeit stufe hält gewährt ruft beschwört punkt punkte".split())
ENGLISH_MARKERS = set("the and to of with for your you this that will chance damage increases reduces deals causes heals target requires level seconds sec armor durability equipped".split())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def quote(text):
    # Decimal control escapes work in Lua 5.1; UTF-8 prose stays byte-for-byte UTF-8.
    return '"' + re.sub(r'[\x00-\x1f\\"]', lambda m: {'"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t'}.get(m[0], '\\%03d' % ord(m[0])), text) + '"'


def literal(value):
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dict):
        return "{ " + ", ".join("[" + quote(str(key)) + "] = " + literal(item) for key,item in value.items()) + " }"
    raise TypeError(type(value))


LUA_READER = r'''
local function q(s)
  return '"' .. tostring(s):gsub('[%z\1-\31\\"]', function(c)
    if c == '"' then return '\\"' end
    if c == '\\' then return '\\\\' end
    return string.format('\\u%04x', string.byte(c))
  end) .. '"'
end
local function emit(t)
  local keys,parts = {},{}
  for k in pairs(t) do keys[#keys+1] = k end
  table.sort(keys, function(a,b) return tostring(a) < tostring(b) end)
  for _,k in ipairs(keys) do
    local v = t[k]
    if type(v) == 'table' then v = emit(v)
    elseif type(v) == 'string' then v = q(v)
    else v = tostring(v) end
    parts[#parts+1] = q(k)..':'..v
  end
  return '{'..table.concat(parts, ',')..'}'
end
local env,addon = {}, {itemData={}, npcData={}, spellData={}}
local chunk,err
if setfenv then chunk,err = loadstring(SOURCE_TEXT, '@MultiLanguage'); if chunk then setfenv(chunk,env) end
else chunk,err = load(SOURCE_TEXT, '@MultiLanguage', 't', env) end
assert(chunk,err)('ReferenceImporter',addon)
print(emit(addon))
'''


def read_source(raw, lua_command):
    script = "local SOURCE_TEXT = " + quote(raw.decode("utf-8-sig")) + "\n" + LUA_READER
    result = subprocess.run(lua_command + ["-"], input=script, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def clean(raw, locale):
    text = html.unescape(raw or "")
    text = re.sub(r"\|H[^|]*\|h(.*?)\|h", r"\1", text, flags=re.S)
    text = re.sub(r"\|T.*?\|t|\|A.*?\|a", "", text, flags=re.S)
    text = re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", text)
    text = re.sub(r"\[q\d*\]", " ", text)
    text = re.sub(r"<(?:br\s*/?|/p)>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:b|i|em|strong|span|div|p)(?:\s+[^>]*)?>", "", text, flags=re.I)
    # Source braces lay out columns; preserve the standard personal-text placeholders.
    text = re.sub(r"\{([^{}]*)\}", lambda m: m[0] if m[1] in ("name","race","class") else m[1], text)
    text = re.sub(r"\{(?:name|race|class)\}|[{}]", lambda m: m[0] if len(m[0]) > 1 else "", text)
    text = re.sub(r"\b(Benötigt|Requires)(?=[A-ZÄÖÜ])", r"\1 ", text)
    text = re.sub(r"\$[gG]([^:;]+):([^;]+);", lambda m: m[1] + " / " + m[2], text)
    text = re.sub(r"\|3-\d+\(([^()]*)\)", r"\1", text)
    text = re.sub(r"\$[bB](?![A-Za-z])", "\n", text)
    for macro,token in [("nN","name"),("rR","race"),("cC","class")]:
        text = re.sub(r"\$["+macro+r"](?![A-Za-z])", "{"+token+"}", text)
    unresolved = False
    marker = "[Quellwert]" if locale == "deDE" else "[source value]"

    def formula(match):
        nonlocal unresolved
        body = match[0][1:-1]
        if re.fullmatch(r"[\d\s().+*/%\-]+", body) and re.search(r"\d",body) and re.search(r"[*+/]",body):
            unresolved = True
            return marker
        return match[0]

    text = re.sub(r"\[[^\]\n]+\]", formula, text)
    if "$" in text:
        unresolved = True
        # Null references carry no learning prose. Known numeric macros never become invented values.
        text = re.sub(r"\$null\b", "", text, flags=re.I)
        text = re.sub(r"\$(?:\d+)?[sSmMdDbBtTuUhHoOxXaAef]\d*", marker, text)
        text = re.sub(r"\$[A-Za-z0-9_]+", marker, text)
        text = re.sub(r"(?<=\])(?=[A-Za-zÄÖÜäöüß])", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text).replace("\r\n","\n").replace("\r","\n")
    text = "\n".join(re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip(), unresolved


def deterministic_gzip(raw):
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(raw)
    return buffer.getvalue()


def developer_reason(name, kind=None):
    if name in ("Add Moogly Radius (PT)", "My Little PROC", "Boss Dummy") or re.fullmatch(r"Copy of Block Value \d+", name):
        return "explicit internal implementation label"
    if kind == "spell" and re.fullmatch(r"Poultry Precision \((?:Guns|Bows|Crossbows)\)(?: \d+| - [A-Za-z ]+)?", name):
        return "spell implementation variant"
    for reason,pattern in DEVELOPER_MARKERS:
        if pattern.search(name):
            return reason


def english_prose(text, english):
    # Only positive long-English evidence is excluded; names and short shared terms are legitimate.
    for segment in re.split(r"(?<=[.!?])\s+|\n+",text):
        words = re.findall(r"[A-Za-zÄÖÜäöüß]+",segment.lower())
        if len(words)>12 and not GERMAN_MARKERS.intersection(words) and len(ENGLISH_MARKERS.intersection(words))>=3:
            return {"reason":"copied English prose" if segment in english else "long English prose with positive English markers", "evidence":segment}


def build(source, lua_command, corpus_path=None):
    if (ROOT / "source-manifest.json").exists():
        current = json.loads((ROOT / "source-manifest.json").read_text(encoding="utf-8"))
        if current.get("sources"):
            raise RuntimeError("Client-specific entity variants are installed. Use import_variants.py; Classic-only regeneration would discard their manifest entries.")
    previous = json.loads((ROOT / "source-manifest.json").read_text(encoding="utf-8")) if not source else None
    if source:
        commit = subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
        assert commit == PIN, "Use the pinned Classic source commit."
        paths = ["Database/"+folder+"/"+locale+".lua" for folder,_ in KINDS.values() for locale in LOCALES]
        subprocess.run(["git","-C",str(source),"diff","--exit-code",PIN,"--"]+paths,capture_output=True,check=True)
    manifest = {
        "schemaVersion": 1, "sourceKey": SOURCE_KEY, "sourceLabel": "MultiLanguage Classic reference",
        "referenceOnly": True, "provenance": {"repo": REPO, "commit": PIN, "branch": "master", "flavor": "Classic source including seasonal additions"},
        "permissionBasis": "Author permission reported by project owner on 2026-10-05; upstream LICENSE remains All rights reserved.",
        "normalization": {"version":1,"formulas":"Retain prose and substitute unevaluated numeric formulas/macros with [Quellwert] / [source value].","scope":"Static learning references; no native gameplay statistics or ENPanel tables are overwritten."},
        "sourceFiles": [], "counts": {}, "runtime_load_order": ["EntityData/Metadata.lua"], "generatedFiles": {},
        "quality": {"version":1,"recordPolicy":"Exclude only explicit QA, DND/DNT, Monster equipment, seasonal internal prefixes, or developer-status names; preserve raw archives, proper names, Radius and legitimate Test of names.","fieldPolicy":"Omit DE prose with over 12 lexical words, at least 3 distinct English markers and no German marker; check individual sentence/line segments, retain DE name and other usable fields.","recordExclusions":[],"fieldExclusions":[]},
    }
    changed,unresolved_total = 0,0
    corpus_rows = []
    for kind,(folder,table) in KINDS.items():
        locales = {}
        manifest["counts"][kind] = {}
        raw_inputs,source_rows = {},{}
        for locale,short in LOCALES.items():
            rel = "Database/"+folder+"/"+locale+".lua"
            archive = ROOT / "Source" / (folder+"-"+locale+".lua.gz")
            raw = (source / rel).read_bytes() if source else gzip.decompress(archive.read_bytes())
            if previous:
                expected = next(file["rawSha256"] for file in previous["sourceFiles"] if file["path"]==rel)
                assert sha(raw)==expected, "Bundled raw source archive hash mismatch."
            raw_inputs[locale],source_rows[locale] = raw,read_source(raw,lua_command)[table][short]
        excluded_ids = {}
        for locale,rows in source_rows.items():
            for key,row in rows.items():
                reason = developer_reason(clean(row.get("name"),locale)[0], kind)
                if reason:
                    excluded_ids[key] = reason
        for key,reason in sorted(excluded_ids.items(),key=lambda pair:int(pair[0])):
            manifest["quality"]["recordExclusions"].append({"kind":kind,"id":int(key),"reason":reason,"sourceNames":{locale:rows[key].get("name") for locale,rows in source_rows.items() if key in rows}})
        for locale,short in LOCALES.items():
            rel = "Database/"+folder+"/"+locale+".lua"
            archive = ROOT / "Source" / (folder+"-"+locale+".lua.gz")
            raw,rows = raw_inputs[locale],source_rows[locale]
            compressed = deterministic_gzip(raw)
            archive.parent.mkdir(parents=True,exist_ok=True)
            archive.write_bytes(compressed)
            manifest["sourceFiles"].append({"path":rel,"url":REPO+"/blob/"+PIN+"/"+rel,"rawSha256":sha(raw),"rawBytes":len(raw),"archive":"EntityData/Source/"+archive.name,"archiveSha256":sha(compressed)})
            clean_rows = {}
            for key,row in sorted(rows.items(),key=lambda pair:int(pair[0])):
                if key in excluded_ids:
                    continue
                name,name_unresolved = clean(row.get("name"),locale)
                if not name:
                    continue
                record = {"name":name}
                has_unresolved = name_unresolved
                for raw_field,field in [("additional_info","text"),("subname","role")]:
                    if row.get(raw_field):
                        text,is_unresolved = clean(row[raw_field],locale)
                        if locale=="deDE" and field in ("text","role") and text:
                            english = clean(source_rows["enUS"].get(key,{}).get(raw_field),"enUS")[0]
                            exclusion = english_prose(text,english)
                            if exclusion:
                                manifest["quality"]["fieldExclusions"].append({"kind":kind,"id":int(key),"locale":locale,"field":field,**exclusion})
                                continue
                        has_unresolved = has_unresolved or is_unresolved
                        if text:
                            record[field] = text
                        if text != row[raw_field]:
                            changed += 1
                if name != row.get("name"):
                    changed += 1
                if has_unresolved:
                    record["unresolvedValues"] = True
                    unresolved_total += 1
                clean_rows[int(key)] = record
                if corpus_path:
                    for field in ("name","text","role"):
                        if record.get(field):
                            corpus_rows.append({"locale":locale,"id":int(key),"kind":kind,"sourceFlavor":SOURCE_KEY,"text":record[field],"category":field})
            locales[locale] = clean_rows
            excluded_count = len(rows.keys() & excluded_ids.keys())
            manifest["counts"][kind][locale] = {"records":len(clean_rows),"text":sum(bool(row.get("text")) for row in clean_rows.values()),"role":sum(bool(row.get("role")) for row in clean_rows.values()),"unresolvedValues":sum(bool(row.get("unresolvedValues")) for row in clean_rows.values()),"sourceRecords":len(rows),"excludedDeveloperRecords":excluded_count,"omittedEmptyNames":len(rows)-len(clean_rows)-excluded_count}
            records = list(clean_rows.items())
            for index,start in enumerate(range(0,len(records),CHUNK)):
                path = ROOT / "Data" / kind / (locale+"_%03d.lua" % index)
                path.parent.mkdir(parents=True,exist_ok=True)
                header = "-- Generated static MultiLanguage Classic reference; see EntityData/source-manifest.json.\nlocal entries = WordHunterWoW_EntityDataBySource["+quote(SOURCE_KEY)+"].kinds["+quote(kind)+"]["+quote(locale)+"]\n"
                body = "".join("entries[%d] = %s\n" % (key,literal(record)) for key,record in records[start:start+CHUNK])
                data = (header+body).encode("utf-8")
                path.write_bytes(data)
                game_path = "EntityData/"+path.relative_to(ROOT).as_posix()
                manifest["runtime_load_order"].append(game_path)
                manifest["generatedFiles"][game_path] = {"sha256":sha(data),"bytes":len(data)}
        de,en = set(locales["deDE"]),set(locales["enUS"])
        manifest["counts"][kind]["coverage"] = {"pairedNames":len(de&en),"deOnly":len(de-en),"enOnly":len(en-de),"pairedText":sum(bool(locales["deDE"][key].get("text")) and bool(locales["enUS"][key].get("text")) for key in de&en),"pairedRoles":sum(bool(locales["deDE"][key].get("role")) and bool(locales["enUS"][key].get("role")) for key in de&en)}
    manifest["normalization"].update(changedFieldValues=changed,recordsWithUnresolvedValues=unresolved_total)
    allowed = set(manifest["runtime_load_order"])
    data_root = (ROOT / "Data").resolve()
    for path in data_root.rglob("*.lua"):
        resolved = path.resolve()
        assert resolved.is_relative_to(data_root), "Generated cleanup must stay inside EntityData/Data."
        if "EntityData/"+path.relative_to(ROOT).as_posix() not in allowed:
            relative = path.relative_to(data_root)
            assert relative.parts[0] in KINDS and re.fullmatch(r"(?:deDE|enUS)_\d{3}\.lua",path.name), "Unexpected non-generated data file; do not delete it."
            path.unlink()
    if corpus_path:
        corpus_path.parent.mkdir(parents=True,exist_ok=True)
        corpus_bytes = ("".join(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n" for row in corpus_rows)).encode("utf-8")
        corpus_path.write_bytes(corpus_bytes)
        manifest["normalizedCorpus"] = {"file":corpus_path.name,"sha256":sha(corpus_bytes),"bytes":len(corpus_bytes),"rows":len(corpus_rows),"rowsByLocale":{locale:sum(row["locale"]==locale for row in corpus_rows) for locale in LOCALES}}
    metadata = "-- Explicit source namespace. Reference text does not describe verified native Forever statistics.\nWordHunterWoW_EntityDataBySource = WordHunterWoW_EntityDataBySource or {}\nlocal ref = "+literal({key:manifest[key] for key in ["schemaVersion","sourceLabel","referenceOnly","provenance","counts"]})+"\nref.kinds = { item = { deDE = {}, enUS = {} }, spell = { deDE = {}, enUS = {} }, npc = { deDE = {}, enUS = {} } }\nWordHunterWoW_EntityDataBySource["+quote(SOURCE_KEY)+"] = ref\n"
    data = metadata.encode("utf-8")
    (ROOT / "Metadata.lua").write_bytes(data)
    manifest["generatedFiles"]["EntityData/Metadata.lua"] = {"sha256":sha(data),"bytes":len(data)}
    (ROOT / "Source" / "UPSTREAM-LICENSE.txt").write_bytes((source / "LICENSE").read_bytes() if source else (ROOT / "Source" / "UPSTREAM-LICENSE.txt").read_bytes())
    (ROOT / "source-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT / "tests").mkdir(exist_ok=True)
    (ROOT / "tests" / "load-order.lua").write_text("return {\n"+"".join("  "+quote(path)+",\n" for path in manifest["runtime_load_order"])+"}\n",encoding="utf-8")
    return manifest


def checks():
    assert clean('[q2]{Waffenhand} {Schwert}\n\n\n[q]Text.',"deDE")[0] == "Waffenhand Schwert\n\nText."
    assert clean('Benötigt[q]Ingenieurskunst Schildhand} Schild {name}', 'deDE')[0] == 'Benötigt Ingenieurskunst Schildhand Schild {name}'
    assert clean('BenötigtRunenschnitzen RequiresEngineering', 'deDE')[0] == 'Benötigt Runenschnitzen Requires Engineering'
    assert clean('$gHeld:Heldin; $n |3-1(Name)',"deDE")[0] == "Held / Heldin {name} Name"
    assert clean('Deals [ 26 * 8 * ( 1 ) ] damage and $3826%.',"enUS") == ('Deals [source value] damage and [source value]%.',True)
    assert clean('$null\n$null',"enUS") == ('',True)
    assert clean('<Random enchantment>',"enUS")[0] == '<Random enchantment>'
    assert clean('|cff123456|Hitem:1|h[Name]|h|r',"enUS")[0] == '[Name]'
    assert developer_reason('QAEnchant Bracer') and developer_reason('Spirit Healer (DND)')
    assert developer_reason('S03Tuning Fireball') and developer_reason('Monster - Sword')
    assert not developer_reason('Radius') and not developer_reason('Test of Faith')
    assert developer_reason('Add Moogly Radius (PT)', 'spell') and developer_reason('Copy of Block Value 20', 'spell')
    assert developer_reason('Poultry Precision (Guns)', 'spell') and not developer_reason('Poultry Precision Scope', 'item')
    assert developer_reason('Poultry Precision (Guns) 1', 'spell') and developer_reason('Poultry Precision (Crossbows) - Auto Shot', 'spell')
    prose='The Crimson Cleaver does not respond to your presence, maybe another class could benefit from this?'
    assert english_prose(prose,prose) and not english_prose('Der Zauber erhöht Eure Stärke und verursacht Schaden.', '')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,help="Pinned MultiLanguage checkout; default rebuilds bundled raw archives.")
    parser.add_argument("--lua",default="lua",help="Lua executable used only by the build-time source reader.")
    parser.add_argument("--corpus",type=Path,help="Optional normalized entity corpus JSONL output, outside runtime files.")
    args = parser.parse_args()
    checks()
    result = build(args.source,[args.lua],args.corpus)
    print(json.dumps({"sourceKey":result["sourceKey"],"counts":result["counts"],"runtimeFiles":len(result["runtime_load_order"]),"normalization":result["normalization"]},ensure_ascii=False))
