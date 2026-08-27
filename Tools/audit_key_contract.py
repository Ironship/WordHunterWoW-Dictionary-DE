#!/usr/bin/env python3
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORDLIST = ROOT / "Data/cache/wordlist_deDE.jsonl"
TRANSLATIONS = ROOT / "Data/cache/translations_de_en.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
LUA = ROOT / "Data/DictionaryDE.lua"
LUA_KEY = re.compile(r'^WordHunterWoW_Dictionary_DE\["((?:\\.|[^"])*)"\]')


def runtime_key(word: str) -> str:
    return word.replace("ẞ", "SS").replace("ß", "ss").lower()


def main():
    words = [json.loads(line) for line in WORDLIST.read_text(encoding="utf-8").splitlines() if line.strip()]
    translations = {}
    for source in (TRANSLATIONS, CURATED):
        for line in source.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("translation"): translations[record["key"]] = record
    lua_keys = set()
    for line in LUA.read_text(encoding="utf-8").splitlines():
        match = LUA_KEY.match(line)
        if match:
            lua_keys.add(match.group(1).replace('\\"', '"').replace('\\\\', '\\'))

    runtime_mismatches, missing_translation, missing_lua = [], [], []
    for record in words:
        generated = record["key"]
        runtime = runtime_key(record["word"])
        if runtime != generated:
            runtime_mismatches.append((record["word"], generated, runtime))
        if generated not in translations:
            missing_translation.append(record["word"])
        if generated not in lua_keys:
            missing_lua.append(record["word"])

    print(f"wordlist={len(words)} translations={len(translations)} lua={len(lua_keys)}")
    print(f"runtime_mismatches={len(runtime_mismatches)} missing_translation={len(missing_translation)} missing_lua={len(missing_lua)}")
    for word, generated, runtime in runtime_mismatches[:50]:
        print(f"MISMATCH {word!r}: generated={generated!r} runtime={runtime!r}")
    for word in missing_translation[:20]: print(f"MISSING_TRANSLATION {word!r}")
    for word in missing_lua[:20]: print(f"MISSING_LUA {word!r}")
    return 1 if runtime_mismatches or missing_translation or missing_lua else 0


if __name__ == "__main__":
    raise SystemExit(main())
