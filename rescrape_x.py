"""Re-scrape only the X handles that previously got rate-limited (HTTP 429).

Serial + jittered delays + exponential backoff on further 429s.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import requests

from scrape import fetch_x, HEADERS  # reuse parser

ROOT = Path(__file__).parent
FILE = ROOT / "artists_enriched.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=30.0,
                    help="seconds to wait between requests (steady pace)")
    ap.add_argument("--cooldown", type=float, default=300.0,
                    help="seconds to pause after a request 429s through all retries")
    ap.add_argument("--retries", type=int, default=3,
                    help="429 retry attempts per artist before deferring")
    args = ap.parse_args()

    with open(FILE) as f:
        artists = json.load(f)

    todo = [
        a for a in artists
        if a.get("x_handle") and not a.get("x_followers")
        and a.get("x_error") in (None, "http:429", "http:503", "no-next-data")
    ]
    # Prioritize artists already known to be popular — sort by current best
    # follower count (IG, since X is mostly missing here) descending.
    def best(a):
        return max(a.get("ig_followers") or 0, a.get("x_followers") or 0)
    todo.sort(key=best, reverse=True)
    print(f"Total: {len(artists)}; to re-fetch X for: {len(todo)} "
          f"(sorted by score; delay={args.delay}s cooldown={args.cooldown}s)", flush=True)

    s = requests.Session()
    fixed = 0
    perma_fail = 0
    for i, art in enumerate(todo, 1):
        h = art["x_handle"]
        r = None
        hit_429 = False
        for attempt in range(args.retries):
            r = fetch_x(h, s)
            if r.get("x_error") == "http:429":
                hit_429 = True
                wait = args.delay * (attempt + 2) + random.uniform(0, 5)
                print(f"  [{i}/{len(todo)}] {art['name'][:30]} 429, sleeping {wait:.0f}s "
                      f"(attempt {attempt+1}/{args.retries})", flush=True)
                time.sleep(wait)
                continue
            break
        art.update(r)
        if r.get("x_followers") is not None and r.get("x_error") is None:
            fixed += 1
        elif r.get("x_error") == "http:429":
            perma_fail += 1
        xf = r.get("x_followers")
        print(f"  [{i}/{len(todo)}] {art['name'][:30]:30s}  X={xf}  "
              f"err={r.get('x_error')}  fixed={fixed} fail={perma_fail}", flush=True)

        # save after every record — slow runs shouldn't risk losing progress
        with open(FILE, "w") as f:
            json.dump(sorted(artists, key=lambda a: a["id"]), f, indent=2, ensure_ascii=False)

        if i == len(todo):
            break
        # If we exhausted retries on a 429, the bucket is drained — take a long
        # cooldown to let it fully refill before resuming the steady pace.
        if r.get("x_error") == "http:429":
            print(f"  -- rate-limited, cooling down {args.cooldown:.0f}s", flush=True)
            time.sleep(args.cooldown)
        else:
            time.sleep(args.delay + random.uniform(0, 5))

    print(f"Done. fixed={fixed} perma_fail={perma_fail}", flush=True)


if __name__ == "__main__":
    main()
