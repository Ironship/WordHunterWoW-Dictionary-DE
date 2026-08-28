#!/usr/bin/env python3
"""Full German audit using direct OpenCode/Kilo JSON subagents.

Muse reviews every entry; Mimo reviews only proposed fixes/status changes.
No agent tool calls: input is attached, output is parsed from JSON events.
"""
import argparse, concurrent.futures, glob, json, os, pathlib, random, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "Data/cache"
TRANSLATIONS = CACHE / "translations_de_en.jsonl"
CURATED = ROOT / "Data/CuratedDE.jsonl"
REVIEWED = CACHE / "fast_audit_reviewed.txt"
BATCH_DIR = CACHE / "fast_audit_batches"
MUSE_DIR = CACHE / "fast_audit_muse"
MIMO_INPUT_DIR = CACHE / "fast_audit_mimo_input"
MIMO_DIR = CACHE / "fast_audit_mimo"

MUSE_PROMPT = """You are a German-English lexicographer auditing World of Warcraft quest vocabulary.
The attached JSONL contains key, word, current translation/note/status, frequency and one real context.
Return ONLY valid UTF-8 JSONL, exactly one object per input key, no fences or prose:
{"key":"...","action":"keep"|"fix","translation":"...","note":"...","status":"keep"|"ignored","confidence":"high"|"medium"|"low"}
Rules:
- Keep unless a correction or genuinely useful common polysemy/grammar note is justified.
- Concise learner gloss, normally <=3 common senses separated by semicolons. Note <=100 chars.
- status=ignored ONLY for clear proper names (characters/places/factions) or non-lexical noises/vocalizations (AAAAh, Uhhh). Never ignore a real common word merely because German capitalizes nouns.
- Preserve existing translation/note when status=ignored unless they need correction.
- Distinguish noun/verb homographs, inflections, separable verbs, passive/future auxiliaries, colloquial forms.
- Do not invent obscure senses from one context. Preserve input key exactly.
"""

MIMO_PROMPT = """You are the conservative second reviewer for a German-English WoW learner dictionary.
The attached JSONL contains original entry and Muse proposal.
Return ONLY valid UTF-8 JSONL, one object per key, no fences/prose:
{"key":"...","action":"accept"|"reject"|"revise","translation":"...","note":"...","status":"keep"|"ignored","confidence":"high"|"medium"|"low"}
Rules:
- Reject unnecessary/obscure/capitalization-only changes. Accept only material learner value.
- status=ignored only for definite proper names or meaningless vocalizations/noise; preserve translations/notes.
- For reject copy current translation/note/status. For accept copy Muse. For revise output final values.
- Gloss <=3 common senses; note <=100 chars. Preserve key exactly.
"""


def find_kilo():
    matches = sorted(glob.glob(str(pathlib.Path.home() / ".vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe")), reverse=True)
    if not matches:
        raise RuntimeError("Kilo CLI not found")
    return matches[0]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def parse_response(stdout):
    chunks = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            chunks.append(event.get("part", {}).get("text", ""))
    text = "".join(chunks).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    if text.startswith("["):
        rows = json.loads(text)
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return rows


def validate(rows, source, phase):
    expected = {row["key"].casefold(): row["key"] for row in source}
    normalized = {}
    required = {"key", "action", "translation", "note", "status", "confidence"}
    for row in rows:
        if not required.issubset(row):
            raise ValueError(f"{phase}: missing fields {required - set(row)}")
        key_cf = str(row["key"]).casefold()
        if key_cf not in expected:
            raise ValueError(f"{phase}: unexpected key {row['key']!r}")
        if key_cf in normalized:
            raise ValueError(f"{phase}: duplicate key {row['key']!r}")
        row["key"] = expected[key_cf]
        if "�" in json.dumps(row, ensure_ascii=False):
            raise ValueError(f"{phase}: replacement character in {row['key']}")
        if len(str(row.get("note") or "")) > 100:
            raise ValueError(f"{phase}: note too long {row['key']}")
        normalized[key_cf] = row
    missing = set(expected) - set(normalized)
    if missing:
        raise ValueError(f"{phase}: missing {len(missing)} keys")
    return [normalized[row["key"].casefold()] for row in source]


def run_model(kilo, model, variant, prompt, source_path, output_path, phase, retries=3):
    source = load_jsonl(source_path)
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "NO_COLOR": "1", "TERM": "dumb"})
    command = [kilo, "run", prompt, "--pure", "--format", "json", "-m", model]
    if variant:
        command += ["--variant", variant]
    command += ["-f", str(source_path)]
    last = None
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
            if result.returncode:
                raise RuntimeError(f"exit={result.returncode}: {result.stderr[-500:]}")
            rows = validate(parse_response(result.stdout), source, phase)
            write_jsonl(output_path, rows)
            return len(rows)
        except Exception as error:
            last = error
            print(f"RETRY {phase} {source_path.name} attempt={attempt}: {error}", flush=True)
            time.sleep(attempt * 5 + random.random() * 8)
    raise RuntimeError(f"{phase} failed {source_path.name}: {last}")


def effective_records():
    records = {}
    for line in TRANSLATIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        if row.get("translation"):
            records[row["key"]] = row
    if CURATED.exists():
        for line in CURATED.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            base = records.get(row["key"], {})
            records[row["key"]] = {**base, **row}
    return records


def prepare_wave(records, reviewed, wave_size, batch_size):
    candidates = [row for key, row in records.items() if key not in reviewed]
    candidates.sort(key=lambda row: (-int(row.get("count") or 0), row["key"]))
    candidates = candidates[:wave_size]
    if BATCH_DIR.exists(): shutil.rmtree(BATCH_DIR)
    if MUSE_DIR.exists(): shutil.rmtree(MUSE_DIR)
    if MIMO_INPUT_DIR.exists(): shutil.rmtree(MIMO_INPUT_DIR)
    if MIMO_DIR.exists(): shutil.rmtree(MIMO_DIR)
    BATCH_DIR.mkdir(parents=True)
    compact = []
    for row in candidates:
        compact.append({
            "key": row["key"], "word": row.get("word") or row["key"],
            "translation": row.get("translation") or "", "note": row.get("note") or "",
            "status": row.get("status") or "new", "count": row.get("count") or 0,
            "context": (row.get("context") or "")[:320],
        })
    paths = []
    for offset in range(0, len(compact), batch_size):
        path = BATCH_DIR / f"batch_{offset // batch_size:03d}.jsonl"
        write_jsonl(path, compact[offset:offset + batch_size])
        paths.append(path)
    return candidates, paths


def collect_mimo_inputs(batch_paths, mimo_batch_size):
    proposals = []
    for path in batch_paths:
        original = {row["key"]: row for row in load_jsonl(path)}
        for muse in load_jsonl(MUSE_DIR / path.name):
            current = original[muse["key"]]
            if muse["action"] == "fix" or muse["status"] == "ignored" or muse.get("note"):
                proposals.append({
                    "key": current["key"], "word": current["word"], "count": current["count"], "context": current["context"],
                    "current_translation": current["translation"], "current_note": current["note"], "current_status": current["status"],
                    "muse_action": muse["action"], "muse_translation": muse["translation"], "muse_note": muse["note"],
                    "muse_status": muse["status"], "muse_confidence": muse["confidence"],
                })
    MIMO_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for offset in range(0, len(proposals), mimo_batch_size):
        path = MIMO_INPUT_DIR / f"batch_{offset // mimo_batch_size:03d}.jsonl"
        write_jsonl(path, proposals[offset:offset + mimo_batch_size])
        paths.append(path)
    return proposals, paths


def apply_reviews(records, mimo_paths):
    curated = {}
    order = []
    if CURATED.exists():
        for row in load_jsonl(CURATED):
            curated[row["key"]] = row
            order.append(row["key"])
    changed = 0
    for path in mimo_paths:
        inputs = {row["key"]: row for row in load_jsonl(path)}
        for review in load_jsonl(MIMO_DIR / path.name):
            if review["confidence"] != "high": continue
            inp = inputs[review["key"]]
            current = records[review["key"]]
            if review["action"] == "reject":
                translation, note = inp["current_translation"], inp["current_note"]
            else:
                translation, note = review["translation"].strip(), review["note"].strip()
            status = "ignored" if review["status"] == "ignored" else current.get("status")
            material = review["action"] != "reject" or status == "ignored"
            if not material: continue
            item = {"key": review["key"], "word": current.get("word") or review["key"], "translation": translation, "note": note}
            if status == "ignored": item["status"] = "ignored"
            if item["key"] not in curated: order.append(item["key"])
            curated[item["key"]] = item
            records[item["key"]] = {**current, **item}
            changed += 1
    write_jsonl(CURATED, [curated[key] for key in order])
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wave-size", type=int, default=3840)
    parser.add_argument("--batch-size", type=int, default=240)
    parser.add_argument("--mimo-batch-size", type=int, default=120)
    parser.add_argument("--parallel", type=int, default=16, help="Fallback parallelism for both models")
    parser.add_argument("--muse-parallel", type=int, default=0)
    parser.add_argument("--mimo-parallel", type=int, default=0)
    parser.add_argument("--reset", action="store_true", help="Audit every entry from scratch")
    parser.add_argument("--max-waves", type=int, default=0, help="Stop after N waves (0 = all)")
    parser.add_argument("--resume-mimo", action="store_true", help="Reuse current prepared/Muse files and resume at Mimo")
    args = parser.parse_args()
    kilo = find_kilo()
    records = effective_records()
    muse_parallel = args.muse_parallel or args.parallel
    mimo_parallel = args.mimo_parallel or args.parallel
    if args.reset and REVIEWED.exists(): REVIEWED.unlink()
    reviewed = set(REVIEWED.read_text(encoding="utf-8").splitlines()) if REVIEWED.exists() else set()
    total = len(records)
    wave = 0
    print(f"FAST AUDIT total={total} reviewed={len(reviewed)} wave_size={args.wave_size} batch={args.batch_size} muse_parallel={muse_parallel} mimo_parallel={mimo_parallel}", flush=True)

    if args.resume_mimo:
        batch_paths = sorted(BATCH_DIR.glob("batch_*.jsonl"))
        if not batch_paths:
            raise RuntimeError("--resume-mimo requested but no prepared batches exist")
        proposals, mimo_paths = collect_mimo_inputs(batch_paths, args.mimo_batch_size)
        print(f"RESUME MIMO: source_batches={len(batch_paths)} proposals={len(proposals)} mimo_batches={len(mimo_paths)}", flush=True)
        if MIMO_DIR.exists(): shutil.rmtree(MIMO_DIR)
        MIMO_DIR.mkdir(parents=True, exist_ok=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=mimo_parallel) as pool:
            futures = [pool.submit(run_model, kilo, "opencode-go/mimo-v2.5", None, MIMO_PROMPT, path, MIMO_DIR / path.name, "mimo") for path in mimo_paths]
            for future in concurrent.futures.as_completed(futures): future.result()
        changed = apply_reviews(records, mimo_paths)
        resumed_rows = [row for path in batch_paths for row in load_jsonl(path)]
        reviewed.update(row["key"] for row in resumed_rows)
        REVIEWED.write_text("\n".join(sorted(reviewed)) + "\n", encoding="utf-8")
        print(f"RESUME MIMO COMPLETE reviewed={len(reviewed)}/{total} changed={changed}", flush=True)
    while len(reviewed) < total:
        wave += 1
        candidates, batch_paths = prepare_wave(records, reviewed, args.wave_size, args.batch_size)
        if not candidates: break
        start = time.time()
        print(f"WAVE {wave}: candidates={len(candidates)} batches={len(batch_paths)} remaining={total-len(reviewed)}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=muse_parallel) as pool:
            futures = [pool.submit(run_model, kilo, "opencode-go/muse-spark-1.2-contributor", "low", MUSE_PROMPT, path, MUSE_DIR / path.name, "muse") for path in batch_paths]
            for future in concurrent.futures.as_completed(futures): future.result()
        proposals, mimo_paths = collect_mimo_inputs(batch_paths, args.mimo_batch_size)
        print(f"WAVE {wave}: Muse done proposals={len(proposals)} mimo_batches={len(mimo_paths)}", flush=True)
        if mimo_paths:
            with concurrent.futures.ThreadPoolExecutor(max_workers=mimo_parallel) as pool:
                futures = [pool.submit(run_model, kilo, "opencode-go/mimo-v2.5", None, MIMO_PROMPT, path, MIMO_DIR / path.name, "mimo") for path in mimo_paths]
                for future in concurrent.futures.as_completed(futures): future.result()
        changed = apply_reviews(records, mimo_paths) if mimo_paths else 0
        reviewed.update(row["key"] for row in candidates)
        REVIEWED.write_text("\n".join(sorted(reviewed)) + "\n", encoding="utf-8")
        elapsed = time.time() - start
        print(f"WAVE {wave} COMPLETE reviewed={len(reviewed)}/{total} changed={changed} elapsed={elapsed:.1f}s rate={len(candidates)/elapsed:.1f}/s", flush=True)
        if wave % 5 == 0:
            subprocess.run(["git", "add", "Data/CuratedDE.jsonl"], cwd=ROOT)
            subprocess.run(["git", "commit", "-m", f"Fast audit checkpoint wave {wave}: {len(reviewed)}/{total}"], cwd=ROOT)
            subprocess.run(["git", "push", "origin", "feat/german-full-audit"], cwd=ROOT)
        if args.max_waves and wave >= args.max_waves:
            break
    subprocess.run([sys.executable, "Tools/build_dictionary_lua.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "Tools/audit_key_contract.py"], cwd=ROOT, check=True)
    print(f"FAST AUDIT COMPLETE reviewed={len(reviewed)}/{total}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
