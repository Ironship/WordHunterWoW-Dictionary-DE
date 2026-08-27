#!/usr/bin/env python3
import argparse, base64, csv, json, pathlib, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
def credentials():
    d = {}
    for line in (ROOT / "Tools/keys.env").read_text(encoding="utf-8").splitlines():
        if "=" in line: k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d["BLIZZARD_CLIENT_ID"], d["BLIZZARD_CLIENT_SECRET"]
def get_token():
    cid, secret = credentials(); auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request("https://oauth.battle.net/token", data=b"grant_type=client_credentials", headers={"Authorization": f"Basic {auth}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["access_token"]
def main():
    p = argparse.ArgumentParser(); p.add_argument("--csv", default=str(ROOT / "Data/QuestV2.csv")); p.add_argument("--cache", default=str(ROOT / "Data/cache/quests_deDE.jsonl")); p.add_argument("--failed", default=str(ROOT / "Data/cache/failed_deDE.txt")); p.add_argument("--workers", type=int, default=6); p.add_argument("--interval", type=float, default=0.25); p.add_argument("--limit", type=int, default=0); args = p.parse_args()
    cache, failed = pathlib.Path(args.cache), pathlib.Path(args.failed); cache.parent.mkdir(parents=True, exist_ok=True); done = set()
    for path, is_json in ((cache, True), (failed, False)):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try: done.add(int(json.loads(line)["id"] if is_json else line))
                except Exception: pass
    with open(args.csv, newline="", encoding="utf-8-sig") as f: ids = [int(r["ID"]) for r in csv.DictReader(f) if r.get("ID")]
    ids = [i for i in ids if i not in done]; ids = ids[:args.limit] if args.limit else ids
    access = get_token(); write_lock = threading.Lock(); rate_lock = threading.Lock(); next_start = [0.0]; count = [len(done)]
    def throttle():
        with rate_lock:
            delay = max(0, next_start[0] - time.monotonic())
            if delay: time.sleep(delay)
            next_start[0] = time.monotonic() + args.interval
    def fetch(qid):
        url = f"https://eu.api.blizzard.com/data/wow/quest/{qid}?namespace=static-eu&locale=de_DE"
        for attempt in range(5):
            throttle()
            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}", "User-Agent": "WordHunterWoW-Dictionary-DE/0.1"})
                d = json.load(urllib.request.urlopen(req, timeout=30)); record = {"id": qid, "title": d.get("title", ""), "description": d.get("description", ""), "objectives": d.get("objectives", "")}
                with write_lock, cache.open("a", encoding="utf-8") as out: out.write(json.dumps(record, ensure_ascii=False) + "\n")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with write_lock, failed.open("a") as out: out.write(f"{qid}\n")
                    break
                if e.code in (429, 500, 502, 503, 504): time.sleep(2 ** attempt); continue
                break
            except Exception: time.sleep(2 ** attempt)
        with write_lock:
            count[0] += 1
            if count[0] % 500 == 0: print(f"processed={count[0]} remaining={len(ids) - (count[0] - len(done))}", flush=True)
    print(f"locale=de_DE total={len(ids)} cached={len(done)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool: list(pool.map(fetch, ids))
    print("done", flush=True)
if __name__ == "__main__": main()
