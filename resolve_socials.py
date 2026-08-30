"""Follow each artist's website (carrd, Linktree, personal site, etc.) to
find their real Instagram/X handles.

FAN EXPO's exhibitor directory gives each Artist Alley entry a single
external URL, and most of those aren't direct social links (see parse.py) -
they're one hop away: a carrd/Linktree page, or a personal site with icons
in the header/footer linking out to Instagram/X. This script fetches each
"website"-only artist's page once and regexes out any instagram.com or
twitter.com/x.com profile links it finds, so scrape.py has a handle to
fetch follower counts for.

Sites that are themselves the platform (Etsy, ArtStation, DeviantArt,
Toyhou.se, Shopify, ...) rarely link back out to IG/X and are left alone -
their `website` field is kept as-is for the site to link out to directly.

Usage:
    python3 resolve_socials.py --workers 8 --resume
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).parent
IN_FILE = ROOT / "artists.json"
OUT_FILE = ROOT / "artists_resolved.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

# Hosts that host the artist's content directly rather than link out to
# their socials - not worth crawling for IG/X links.
SKIP_HOSTS = {
    "etsy.com", "artstation.com", "deviantart.com", "toyhou.se",
    "myshopify.com", "square.site", "myportfolio.com",
}

INSTAGRAM_HREF = re.compile(
    r'instagram\.com/([A-Za-z0-9_.]+)/?(?:["\'\s?#])', re.IGNORECASE
)
TWITTER_HREF = re.compile(
    r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)/?(?:["\'\s?#])', re.IGNORECASE
)
# handles that are UI chrome, not a profile
IG_BLOCKLIST = {"p", "reel", "explore", "accounts", "share", "stories", "tv"}
X_BLOCKLIST = {"share", "intent", "home", "search", "i", "hashtag"}


def should_skip(url: str) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return any(host == h or host.endswith("." + h) for h in SKIP_HOSTS)


def find_handles(text: str) -> tuple[str | None, str | None]:
    ig = None
    for m in INSTAGRAM_HREF.finditer(text):
        h = m.group(1)
        if h.lower() not in IG_BLOCKLIST:
            ig = h
            break
    x = None
    for m in TWITTER_HREF.finditer(text):
        h = m.group(1)
        if h.lower() not in X_BLOCKLIST:
            x = h
            break
    return ig, x


def resolve_one(artist: dict, session: requests.Session) -> dict:
    result = dict(artist)
    url = artist.get("website")
    if not url or artist.get("ig_handle") or artist.get("x_handle"):
        return result
    if should_skip(url):
        return result
    try:
        r = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        result["resolve_error"] = f"{e.__class__.__name__}:{e}"
        return result
    ig, x = find_handles(r.text)
    if ig:
        result["ig_handle"] = ig
    if x:
        result["x_handle"] = x
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_file", default=str(IN_FILE))
    ap.add_argument("--out", default=str(OUT_FILE))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    with open(args.in_file, encoding="utf-8") as f:
        artists = json.load(f)
    if args.limit:
        artists = artists[: args.limit]

    out_path = Path(args.out)
    existing: dict[int, dict] = {}
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for a in json.load(f):
                existing[a["id"]] = a

    todo = [a for a in artists if a["id"] not in existing]
    print(f"Total: {len(artists)}; cached: {len(existing)}; to resolve: {len(todo)}")

    results = list(existing.values())
    done = len(existing)
    save_every = 20

    def _save():
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sorted(results, key=lambda a: a["id"]), f, indent=2, ensure_ascii=False)

    def _work(a):
        s = requests.Session()
        r = resolve_one(a, s)
        time.sleep(random.uniform(0.3, 0.8))
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_work, a): a for a in todo}
        for fut in as_completed(futs):
            artist = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = dict(artist)
                r["resolve_error"] = f"{e.__class__.__name__}:{e}"
            results.append(r)
            done += 1
            found = "ig" if r.get("ig_handle") else ("x" if r.get("x_handle") else "-")
            print(f"[{done}/{len(artists)}] {artist['name'][:30]:30s}  found={found}", flush=True)
            if done % save_every == 0:
                _save()

    _save()
    total = len(results)
    newly_ig = sum(1 for a in results if a.get("ig_handle") and not any(
        o["id"] == a["id"] and o.get("ig_handle") for o in artists
    ))
    print(f"Wrote {total} artists -> {out_path}")
    print(f"  newly found IG handles: {newly_ig}")


if __name__ == "__main__":
    main()
