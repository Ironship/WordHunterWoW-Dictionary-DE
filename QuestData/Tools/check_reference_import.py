"""Check that every pinned source ID/field is accepted or explicitly excluded.

This independent ledger check does not repeat the importer's cleanup algorithm.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

FLAVORS = {"multilanguage-classic-master": "classic", "multilanguage-tbc": "tbc",
           "multilanguage-retail": "retail"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(audit, questdata, corpus_path):
    manifest = json.loads((questdata / "source-manifest.json").read_text(encoding="utf-8"))
    report, corpus, summary = manifest["referenceSources"], {}, {}
    for line in corpus_path.open(encoding="utf-8"):
        row = json.loads(line)
        fields = corpus.setdefault((row["sourceFlavor"], row["locale"]), {}).setdefault(row["id"], {})
        assert row["category"] not in fields, "duplicate source field"
        fields[row["category"]] = row["text"]
    for source, info in report["sources"].items():
        for locale, stats in info["locales"].items():
            path = audit / f"extracted/ml-{FLAVORS[source]}-{'de' if locale == 'deDE' else 'en'}.jsonl"
            originals = {row["id"]: row for row in (json.loads(line) for line in path.open(encoding="utf-8"))}
            kept, exclusions = corpus[(source, locale)], stats["excluded"]
            gone = {row["id"] for row in exclusions if row["field"] == "record"}
            assert set(originals) == set(kept) | gone and not (set(kept) & gone)
            assert len(kept) == stats["retainedRecords"]
            expected = {(qid, field) for qid, row in originals.items() if qid not in gone
                        for field in ("title", "description", "objective", "progress", "completion")
                        if str(row.get(field) or "").strip()}
            exposed = {(qid, "objective" if field in ("objectives", "sourceObjective") else field)
                       for qid, fields in kept.items() for field in fields}
            removed = {(row["id"], row["field"]) for row in exclusions
                       if row["id"] not in gone and row["field"] != "record"}
            assert not (exposed & removed), "field simultaneously imported and excluded"
            assert expected == exposed | removed, "source field was silently lost or invented"
            actual = collections.Counter(field for fields in kept.values() for field in fields)
            assert dict(actual) == stats["fields"]
            summary[source + " " + locale] = {"records": len(kept), "fields": sum(actual.values()),
                                              "excludedRecords": len(gone), "excludedFields": len(removed)}
    assert all(sha(questdata / name) == expected for name, expected in manifest["files"].items())
    assert set(report["files"]) == {"ReferenceMetadata.lua"} | {
        path.relative_to(questdata).as_posix() for path in (questdata / "References").rglob("*.lua")}
    return {"status": "PASS", "sourceIdsAndFieldsAccountedExactlyOnce": True,
            "allManifestFileHashesMatch": True, "noStaleReferenceChunks": True,
            "corpusSha256": sha(corpus_path), "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--questdata", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = check(args.audit, args.questdata, args.corpus)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
