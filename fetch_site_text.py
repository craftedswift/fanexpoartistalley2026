"""Fetch a short text snapshot of each artist's website for categorization.

Pulls <title>, meta description, and the first chunk of visible body text
from each artist's `website` link (or, for handle-only artists, tries their
IG/X profile URL directly). Output feeds an LLM classification pass that
tags each artist with what they sell (prints, stickers, plush, etc) - FAN
EXPO's own exhibitor data has no such field (see parse.py).

Usage:
    python3 fetch_site_text.py --resume
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).parent
IN_FILE = ROOT / "artists_enriched.json"
OUT_FILE = ROOT / "artists_site_text.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
ALLTAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', re.IGNORECASE
)


def extract_text(html: str, max_chars: int = 1200) -> dict:
    title_m = TITLE_RE.search(html)
    title = WS_RE.sub(" ", title_m.group(1)).strip() if title_m else None
    desc_m = DESC_RE.search(html)
    desc = WS_RE.sub(" ", desc_m.group(1)).strip() if desc_m else None
    body = TAG_RE.sub(" ", html)
    body = ALLTAG_RE.sub(" ", body)
    body = WS_RE.sub(" ", body).strip()
    return {"title": title, "meta_desc": desc, "body": body[:max_chars]}


def fetch_one(artist: dict) -> dict:
    out = {"id": artist["id"], "name": artist["name"], "site_text": None, "site_error": None}
    url = artist.get("website")
    if not url:
        return out
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    except Exception as e:
        out["site_error"] = f"req:{e.__class__.__name__}"
        return out
    if r.status_code != 200:
        out["site_error"] = f"http:{r.status_code}"
        return out
    try:
        out["site_text"] = extract_text(r.text)
    except Exception as e:
        out["site_error"] = f"parse:{e.__class__.__name__}"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_file", default=str(IN_FILE))
    ap.add_argument("--out", default=str(OUT_FILE))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    with open(args.in_file, encoding="utf-8") as f:
        artists = json.load(f)
    artists = [a for a in artists if a.get("website")]
    if args.limit:
        artists = artists[: args.limit]

    out_path = Path(args.out)
    existing: dict[int, dict] = {}
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for a in json.load(f):
                existing[a["id"]] = a

    todo = [a for a in artists if a["id"] not in existing]
    print(f"Total with website: {len(artists)}; cached: {len(existing)}; to fetch: {len(todo)}")

    results = list(existing.values())
    save_every = 25

    def _save():
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sorted(results, key=lambda a: a["id"]), f, indent=2, ensure_ascii=False)

    def _work(a):
        r = fetch_one(a)
        time.sleep(random.uniform(0.2, 0.5))
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_work, a): a for a in todo}
        done = len(existing)
        for fut in as_completed(futs):
            artist = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"id": artist["id"], "name": artist["name"], "site_text": None,
                     "site_error": f"exc:{e.__class__.__name__}"}
            results.append(r)
            done += 1
            status = "ok" if r.get("site_text") else r.get("site_error")
            print(f"[{done}/{len(artists)}] {artist['name']:<30} {status}")
            if done % save_every == 0:
                _save()

    _save()
    print(f"Wrote {len(results)} entries -> {out_path}")


if __name__ == "__main__":
    main()
