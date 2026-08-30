"""Scrape Instagram + Twitter/X follower counts for each artist.

IG: og:description meta tag on the public profile page works without login.
X: syndication.twitter.com embed endpoint returns followers_count as JSON
   embedded in the page. (x.com itself is fully gated.)
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).parent
IN_FILE = ROOT / "artists.json"
OUT_FILE = ROOT / "artists_enriched.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
}

IG_PATTERN = re.compile(
    r'([0-9][0-9,\.]*)\s*([KMB]?)\s*Followers,\s*([0-9][0-9,\.]*)\s*([KMB]?)\s*Following,\s*([0-9][0-9,\.]*)\s*([KMB]?)\s*Posts',
    re.IGNORECASE,
)
IG_OG_DESC = re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.IGNORECASE)
IG_OG_IMAGE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]*)"', re.IGNORECASE)
X_FOLLOWERS = re.compile(r'"followers_count"\s*:\s*([0-9]+)')
X_PROFILE_IMG = re.compile(r'"profile_image_url_https"\s*:\s*"([^"]+)"')
X_NAME = re.compile(r'"name"\s*:\s*"([^"]+)"\s*,\s*"screen_name"\s*:\s*"([^"]+)"')


def _parse_count(num: str, suffix: str) -> int | None:
    try:
        n = float(num.replace(",", ""))
    except ValueError:
        return None
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix.upper(), 1)
    return int(round(n * mult))


def fetch_instagram(handle: str, session: requests.Session) -> dict:
    out: dict = {"ig_followers": None, "ig_profile_pic": None, "ig_error": None}
    if not handle:
        return out
    url = f"https://www.instagram.com/{handle}/"
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        out["ig_error"] = f"req:{e.__class__.__name__}"
        return out
    if r.status_code != 200:
        out["ig_error"] = f"http:{r.status_code}"
        return out
    text = r.text
    m = IG_OG_DESC.search(text)
    if not m:
        out["ig_error"] = "no-og-desc"
        return out
    desc = html.unescape(m.group(1))
    # "29K Followers, 147 Following, 107 Posts - See Instagram photos and videos..."
    fm = IG_PATTERN.search(desc)
    if fm:
        out["ig_followers"] = _parse_count(fm.group(1), fm.group(2))
    else:
        # Empty profile or different format. Treat as found but 0/unknown.
        out["ig_error"] = "no-pattern"
    pi = IG_OG_IMAGE.search(text)
    if pi:
        out["ig_profile_pic"] = html.unescape(pi.group(1))
    return out


def _walk_users(o):
    if isinstance(o, dict):
        if "screen_name" in o and "followers_count" in o:
            yield o
        for v in o.values():
            yield from _walk_users(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_users(v)


def fetch_x(handle: str, session: requests.Session) -> dict:
    out: dict = {"x_followers": None, "x_profile_pic": None, "x_name": None, "x_error": None}
    if not handle:
        return out
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        out["x_error"] = f"req:{e.__class__.__name__}"
        return out
    if r.status_code != 200:
        out["x_error"] = f"http:{r.status_code}"
        return out
    text = r.text
    nd = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.DOTALL)
    if not nd:
        out["x_error"] = "no-next-data"
        return out
    try:
        data = json.loads(nd.group(1))
    except Exception as e:
        out["x_error"] = f"json:{e.__class__.__name__}"
        return out
    handle_lc = handle.lower()
    candidates = [u for u in _walk_users(data) if u.get("screen_name", "").lower() == handle_lc]
    if not candidates:
        out["x_error"] = "user-not-found"
        return out
    # All copies should agree; take the one with the most populated record.
    target = max(candidates, key=lambda u: len(u))
    out["x_followers"] = int(target.get("followers_count") or 0)
    pic = target.get("profile_image_url_https")
    if pic:
        out["x_profile_pic"] = pic.replace("_normal.", "_400x400.")
    out["x_name"] = target.get("name")
    return out


def enrich_one(artist: dict) -> dict:
    s = requests.Session()
    result = dict(artist)
    if artist.get("ig_handle"):
        result.update(fetch_instagram(artist["ig_handle"], s))
        time.sleep(random.uniform(0.4, 0.9))
    if artist.get("x_handle"):
        result.update(fetch_x(artist["x_handle"], s))
        time.sleep(random.uniform(0.4, 0.9))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only process the first N artists (0=all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--resume", action="store_true", help="skip artists already in output")
    ap.add_argument("--in", dest="in_file", default=str(IN_FILE), help="input JSON (artists.json or artists_resolved.json)")
    ap.add_argument("--out", default=str(OUT_FILE))
    args = ap.parse_args()

    out_path = Path(args.out)
    with open(args.in_file, encoding="utf-8") as f:
        artists = json.load(f)
    if args.limit:
        artists = artists[: args.limit]

    existing: dict[int, dict] = {}
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for a in json.load(f):
                existing[a["id"]] = a

    todo = [a for a in artists if a["id"] not in existing]
    print(f"Total in input: {len(artists)}; cached: {len(existing)}; to fetch: {len(todo)}")

    results = list(existing.values())
    done = len(existing)
    save_every = 20

    def _save():
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sorted(results, key=lambda a: a["id"]), f, indent=2, ensure_ascii=False)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(enrich_one, a): a for a in todo}
        for fut in as_completed(futs):
            artist = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = dict(artist)
                r["scrape_error"] = f"{e.__class__.__name__}:{e}"
            results.append(r)
            done += 1
            ig = r.get("ig_followers")
            xf = r.get("x_followers")
            print(
                f"[{done}/{len(artists)}] {artist['name'][:30]:30s}  IG={ig}  X={xf}",
                flush=True,
            )
            if done % save_every == 0:
                _save()

    _save()
    print(f"Wrote {len(results)} artists -> {out_path}")


if __name__ == "__main__":
    main()
