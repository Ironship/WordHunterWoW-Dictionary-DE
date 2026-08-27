#!/usr/bin/env python3
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "Data/cache/translations_de_en.jsonl"
PATCH_DIR = ROOT / "Data/cache/audit_patches"

def main():
    patches = {}
    for path in sorted(PATCH_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            key = rec.get("key")
            if not key:
                continue
            if rec.get("action") == "keep":
                continue
            patches[key] = rec
    if not patches:
        print("patches=0")
        return 0
    out_lines = []
    changed = 0
    for line in SRC.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        patch = patches.get(rec["key"])
        if patch:
            if "translation" in patch and patch["translation"]:
                rec["translation"] = patch["translation"]
            if "note" in patch:
                rec["note"] = patch["note"]
            changed += 1
        out_lines.append(json.dumps(rec, ensure_ascii=False))
    SRC.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"applied={changed} unique_patches={len(patches)}")


if __name__ == "__main__":
    sys.exit(main() or 0)
