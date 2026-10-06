"""Decode the pinned next-batch Lua literals into deterministic JSONL (requires lupa).

The Lua 5.1 chunks run with an empty data-only environment: no io/os/require/game
APIs. Raw immutable Git blob IDs are checked before executing any source chunk.
This tool reads local snapshots; it does not fetch, translate or generate audio.
"""
import argparse
import hashlib
import json
from pathlib import Path

from lupa.lua51 import LuaRuntime
from import_multilanguage_references import NEXT_INPUTS, export_name


def export(inputs):
    lua = LuaRuntime(unpack_returned_tuples=True)
    decode = lua.eval('''function(text)
        local env = {MultiLanguageQuestData = {}}
        local addon = {questData = {}}
        local chunk = assert(loadstring(text))
        setfenv(chunk, env)
        chunk("MultiLanguage", addon)
        return addon.questData, env.MultiLanguageQuestData
    end''')
    output = inputs / "extracted"
    output.mkdir(parents=True, exist_ok=True)
    files = []
    for (flavor, locale), (relative, expected_blob, expected_export) in NEXT_INPUTS.items():
        raw = (inputs / relative).read_bytes()
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        assert blob == expected_blob, "pinned raw source changed: " + relative
        addon, globals_table = decode(raw.decode("utf-8-sig"))
        language = "de" if locale == "deDE" else "en"
        rows = addon[language] or globals_table[language]
        assert rows is not None, "expected language table absent"
        records = []
        for qid, fields in rows.items():
            assert isinstance(qid, (int, float)) and qid > 0 and int(qid) == qid
            row = {"id": int(qid)}
            for field, value in fields.items():
                assert isinstance(field, str) and isinstance(value, (str, int, float, bool))
                row[field] = value
            records.append(row)
        records.sort(key=lambda row: row["id"])
        payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                          + "\n" for row in records).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        assert digest == expected_export, "unexpected decoded export: " + relative
        name = export_name(flavor, locale)
        (output / name).write_bytes(payload)
        files.append({"name": name, "records": len(records), "sha256": digest, "rawPath": relative})
    report = {"decoder": "sandboxed Lua 5.1 via lupa.lua51; data-only environment; sorted IDs and JSON keys",
              "files": files}
    (inputs / "export-provenance.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    print(json.dumps(export(parser.parse_args().inputs)))
