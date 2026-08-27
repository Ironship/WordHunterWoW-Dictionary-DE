#!/usr/bin/env python3
import argparse, json, pathlib, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
def main():
    p = argparse.ArgumentParser(); p.add_argument("--wordlist", default=str(ROOT / "Data/cache/wordlist_deDE.jsonl")); p.add_argument("--cache", default=str(ROOT / "Data/cache/translations_de_en.jsonl")); p.add_argument("--workers", type=int, default=4); p.add_argument("--interval", type=float, default=0.25); p.add_argument("--limit", type=int, default=0); args = p.parse_args()
    target = pathlib.Path(args.cache); target.parent.mkdir(parents=True, exist_ok=True); done = {}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            try: r = json.loads(line); done[r["key"]] = r
            except Exception: pass
    records = [json.loads(line) for line in pathlib.Path(args.wordlist).read_text(encoding="utf-8").splitlines()]
    records = [r for r in records if r["key"] not in done]; records = records[:args.limit] if args.limit else records
    lock = threading.Lock(); rate = threading.Lock(); next_start = [0.0]; count = [len(done)]
    def throttle():
        with rate:
            delay = max(0, next_start[0] - time.monotonic())
            if delay: time.sleep(delay)
            next_start[0] = time.monotonic() + args.interval
    def translate(r):
        throttle(); params = urllib.parse.urlencode({"client": "dict-chrome-ex", "sl": "de", "tl": "en", "q": r["word"]})
        try:
            request = urllib.request.Request("https://clients5.google.com/translate_a/t?" + params, headers={"User-Agent": "Mozilla/5.0"})
            data = json.load(urllib.request.urlopen(request, timeout=20))
            if isinstance(data, str): translation = data.strip()
            elif isinstance(data, list) and data and isinstance(data[0], str): translation = data[0].strip()
            else: translation = ""
        except Exception: translation = ""
        result = {**r, "translation": translation, "note": ""}
        with lock, target.open("a", encoding="utf-8") as out: out.write(json.dumps(result, ensure_ascii=False) + "\n")
        with lock:
            count[0] += 1
            if count[0] % 500 == 0: print(f"translated={count[0]} remaining={len(records) - (count[0] - len(done))}", flush=True)
    print(f"to_translate={len(records)} cached={len(done)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool: list(pool.map(translate, records))
if __name__ == "__main__": main()
