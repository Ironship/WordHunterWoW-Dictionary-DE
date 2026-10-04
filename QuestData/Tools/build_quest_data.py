"""Build Dictionary-DE's bundled quest data from pinned Classic JSONL and WDB.

Reads source caches only. The destination must be explicitly selected.
Native WDB text decoding accepts one unique, complete, UTF-8 text tail;
it never assumes a fixed offset after the variable quest objective data.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import struct

PF_COMMIT = "104f35678ca39ab1fb78b655f815cc7016f5e0c8"
FIELDS = ("title", "objectives", "description", "areaDescription",
          "portraitGiverText", "portraitGiverName", "portraitTurnInText",
          "portraitTurnInName", "completionLog")
WIDTHS = (9, 12, 12, 9, 10, 8, 10, 8, 11)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalize(text):
    # These are Blizzard's paragraph markers, not text to translate or invent.
    return str(text or "").replace("$B", "\n").replace("$b", "\n")


def decode_tail(payload):
    candidates = []
    for start in range(12, len(payload)):
        # 89 length bits + two flag bits + five zero padding bits.
        if payload[start - 1] & 31:
            continue
        bits = "".join(f"{byte:08b}" for byte in payload[start - 12:start])
        offset, lengths = 0, []
        for width in WIDTHS:
            lengths.append(int(bits[offset:offset + width], 2))
            offset += width
        if not lengths[0] or sum(lengths) != len(payload) - start:
            continue
        position, texts = start, []
        try:
            for length in lengths:
                text = payload[position:position + length].decode("utf-8")
                if any(not (char.isprintable() or char in "\r\n\t") for char in text):
                    raise ValueError("nontext byte")
                texts.append(text)
                position += length
        except (UnicodeDecodeError, ValueError):
            continue
        if texts[0].strip():
            candidates.append((start, dict(zip(FIELDS, texts))))
    if len(candidates) != 1:
        raise ValueError(f"expected one complete text tail, found {len(candidates)}")
    return candidates[0]


def read_wdb(path, locale):
    data = path.read_bytes()
    magic, build, stored_locale, _, record_version, cache_version = struct.unpack_from("<4sI4sIII", data)
    if magic != b"TSQW" or stored_locale[::-1].decode("ascii") != locale:
        raise ValueError("unexpected WDB magic or locale")
    if not 70000 <= build < 71000:
        raise ValueError("this decoder was validated only for Forever build 70xxx")
    offset, records, evidence = 24, {}, []
    while offset + 8 <= len(data):
        qid, length = struct.unpack_from("<ii", data, offset)
        if qid == 0 and length == 0:
            break
        if qid <= 0 or length < 12 or offset + 8 + length > len(data):
            raise ValueError(f"invalid frame at {offset}")
        payload = data[offset + 8:offset + 8 + length]
        if struct.unpack_from("<i", payload)[0] != qid:
            raise ValueError("inner quest ID mismatch")
        start, texts = decode_tail(payload)
        if qid in records:
            raise ValueError("duplicate quest ID")
        records[qid] = {
            key: normalize(texts[key]) for key in ("title", "description", "objectives")
        }
        records[qid].update(source=f"native Forever {locale} questcache.wdb build {build}",
                            flavor="forever", originFlavor="forever", locale=locale,
                            sourceBuild=build, sourceHash=digest(payload))
        evidence.append(dict(id=qid, frameOffset=offset, payloadBytes=length,
                             textOffset=start, payloadSha256=digest(payload)))
        offset += 8 + length
    if data[offset:] != b"\0" * 8:
        raise ValueError("WDB must end at an exact eight-byte null terminator")
    return records, dict(path=path.name, sha256=digest(data), bytes=len(data), build=build,
                         locale=locale, recordVersion=record_version, cacheVersion=cache_version,
                         records=len(records), decoded=evidence)


def read_classic(path, locale, allowed):
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["id"] not in allowed:
            continue
        if row["id"] in records or row.get("locale") != locale or row.get("flavor") != "classic":
            raise ValueError("duplicate ID or wrong Classic source locale/flavor")
        records[row["id"]] = {key: normalize(row.get(key)) for key in ("title", "description", "objectives")}
        records[row["id"]].update(source="pfQuest Vanilla " + PF_COMMIT, flavor="classic",
                                   originFlavor="classic", locale=locale)
    if set(records) != allowed:
        raise ValueError("pinned source does not cover the selected Classic IDs")
    return records


def quote(text):
    escaped = []
    for char in str(text):
        if char == "\\": escaped.append("\\\\")
        elif char == '"': escaped.append('\\"')
        elif char == "\n": escaped.append("\\n")
        elif char == "\r": escaped.append("\\r")
        elif char == "\t": escaped.append("\\t")
        elif ord(char) < 32: escaped.append("\\" + f"{ord(char):03d}")
        else: escaped.append(char)
    return '"' + "".join(escaped) + '"'


def write_chunks(out, flavor, locale, records, names):
    ordered = sorted(records.items())
    for start in range(0, len(ordered), 250):
        name = f"Data/{flavor}/{locale}_{start // 250:03d}.lua"
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["WordHunterWoW_QuestDataByFlavor = WordHunterWoW_QuestDataByFlavor or {}",
                 f"WordHunterWoW_QuestDataByFlavor.{flavor} = WordHunterWoW_QuestDataByFlavor.{flavor} or {{}}",
                 f"WordHunterWoW_QuestDataByFlavor.{flavor}.{locale} = WordHunterWoW_QuestDataByFlavor.{flavor}.{locale} or {{}}",
                 f"local quests = WordHunterWoW_QuestDataByFlavor.{flavor}.{locale}"]
        for qid, row in ordered[start:start + 250]:
            values = [key + " = " + (str(value) if isinstance(value, int) else quote(value))
                      for key, value in row.items()]
            lines.append(f"quests[{qid}] = {{ " + ", ".join(values) + " }")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        names.append(name)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--classic-de", type=pathlib.Path, required=True)
    p.add_argument("--classic-en", type=pathlib.Path, required=True)
    p.add_argument("--classic-ids", type=pathlib.Path, required=True)
    p.add_argument("--wdb-de", type=pathlib.Path, required=True)
    p.add_argument("--wdb-en", type=pathlib.Path, required=True)
    p.add_argument("--license", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    args = p.parse_args()
    allowed = set(json.loads(args.classic_ids.read_text(encoding="utf-8")))
    classic = {"deDE": read_classic(args.classic_de, "deDE", allowed),
               "enUS": read_classic(args.classic_en, "enUS", allowed)}
    untranslated = {"description": [], "objectives": []}
    for qid, german in classic["deDE"].items():
        english = classic["enUS"][qid]
        for field in untranslated:
            if german[field] and german[field] == english[field]:
                german[field] = ""
                untranslated[field].append(qid)
    native, wdb_evidence = {}, {}
    for locale, path in (("deDE", args.wdb_de), ("enUS", args.wdb_en)):
        native[locale], wdb_evidence[locale] = read_wdb(path, locale)
    args.out.mkdir(parents=True, exist_ok=True)
    names = []
    for locale in ("deDE", "enUS"):
        write_chunks(args.out, "classic", locale, classic[locale], names)
    names.append("SeedForever.lua")
    seed = '''-- Classic texts are an explicit compatibility fallback on Forever.
-- Native Forever records below replace these copies without touching Classic.
local data = WordHunterWoW_QuestDataByFlavor
data.forever = data.forever or {}
for _, locale in ipairs({"deDE", "enUS"}) do
    data.forever[locale] = data.forever[locale] or {}
    for id, record in pairs(data.classic[locale]) do
        if not data.forever[locale][id] then
            local copy = {}
            for key, value in pairs(record) do copy[key] = value end
            copy.flavor = "forever"
            copy.originFlavor = "classic"
            copy.compatibleClassic = true
            data.forever[locale][id] = copy
        end
    end
end
'''
    (args.out / "SeedForever.lua").write_bytes(seed.encode("utf-8"))
    for locale in ("deDE", "enUS"):
        write_chunks(args.out, "forever", locale, native[locale], names)
    names.append("Loader.lua")
    loader = '''-- OptionalDeps ensures ENPanel's chunks are loaded before this alias.
local function selectFlavor()
    local addon = WordHunterWoW_Addon
    local compat = addon and addon.Compat
    local flavor = compat and compat.GameFlavor and compat.GameFlavor()
    if flavor ~= "classic" and flavor ~= "forever" then return end
    local data = WordHunterWoW_QuestDataByFlavor[flavor]
    if data and data.enUS then WordHunterWoW_QuestEN = data.enUS end
end
selectFlavor()
-- The base resolves season/client flavor again at login.
local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", selectFlavor)
'''
    (args.out / "Loader.lua").write_bytes(loader.encode("utf-8"))
    shutil.copyfile(args.license, args.out / "LICENSE")
    tools = args.out / "Tools"
    tools.mkdir(exist_ok=True)
    if pathlib.Path(__file__).resolve() != (tools / "build_quest_data.py").resolve():
        shutil.copyfile(__file__, tools / "build_quest_data.py")
    counts = {}
    for locale in ("deDE", "enUS"):
        forever = dict(classic[locale]); forever.update(native[locale])
        counts[locale] = {"classic": len(classic[locale]), "nativeForever": len(native[locale]),
                          "foreverUnion": len(forever),
                          "classicDescription": sum(bool(r["description"]) for r in classic[locale].values()),
                          "classicObjectives": sum(bool(r["objectives"]) for r in classic[locale].values())}
    metadata = dict(pfQuestCommit=PF_COMMIT, allowedClassicIds=len(allowed), counts=counts,
                    untranslatedGermanFieldsRemoved=untranslated,
                    wdb=wdb_evidence, files={name: digest((args.out / name).read_bytes()) for name in names})
    (args.out / "source-manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
