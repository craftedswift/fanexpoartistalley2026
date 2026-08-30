"""Parse the FAN EXPO Canada 2026 exhibitor directory into a clean JSON.

FAN EXPO's site (an Encore/KNect365-style SPA) ships its full exhibitor
data as a JSON blob assigned to `window.__REDUX_STORE__` inside the page
HTML. Rather than scrape the rendered table (which has no category info),
we pull that JSON directly: `siteContent.data.sections[*].sponsorsCategories`
holds one entry per category ("Artist Alley", "Retailer", "Corporate", ...),
each with a flat list of organisations: {name, path, url, location, ...}.

Unlike Anime Expo's page, FAN EXPO exhibitors list a single external URL
each (sometimes a direct Instagram/X profile, more often a personal site,
carrd, Linktree, Etsy, ArtStation, etc.). We classify that URL by host;
anything that isn't a direct IG/X link is kept as `website` for
resolve_socials.py to follow up on.

Usage:
    python3 parse.py "/path/to/Exhibitor Directory - FAN EXPO Canada.htm"
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
OUT = ROOT / "artists.json"
CATEGORY = "Artist Alley"

REDUX_MARKER = "window.__REDUX_STORE__ = "

INSTAGRAM_RE = re.compile(r"instagram(?:\.com)?/([A-Za-z0-9_.]+)", re.IGNORECASE)
TWITTER_RE = re.compile(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)", re.IGNORECASE)


def extract_redux_store(html: str) -> dict:
    start = html.find(REDUX_MARKER)
    if start == -1:
        raise ValueError("couldn't find window.__REDUX_STORE__ in the saved page")
    start += len(REDUX_MARKER)
    return json.JSONDecoder().raw_decode(html, start)[0]


def find_sponsor_categories(store: dict) -> list[dict]:
    sections = store["siteContent"]["data"]["sections"]
    for section in sections:
        if "sponsorsCategories" in section:
            return section["sponsorsCategories"]
    raise ValueError("no section with sponsorsCategories found")


def handle_from_url(url: str, pattern: re.Pattern) -> str | None:
    m = pattern.search(url)
    if not m:
        return None
    return m.group(1).strip().rstrip("/") or None


def classify(url: str | None) -> tuple[str | None, str | None, str | None]:
    """Returns (ig_handle, x_handle, website)."""
    if not url:
        return None, None, None
    ig = handle_from_url(url, INSTAGRAM_RE)
    if ig:
        return ig, None, None
    x = handle_from_url(url, TWITTER_RE)
    if x:
        return None, x, None
    return None, None, url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="saved FAN EXPO exhibitor directory .htm/.html file")
    ap.add_argument("--category", default=CATEGORY)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    html = Path(args.src).read_text(encoding="utf-8", errors="ignore")
    store = extract_redux_store(html)
    categories = find_sponsor_categories(store)

    matched = [c for c in categories if c.get("title") == args.category]
    if not matched:
        available = ", ".join(repr(c.get("title")) for c in categories)
        raise SystemExit(f"category {args.category!r} not found. Available: {available}")

    orgs = matched[0].get("organisations", [])
    artists = []
    for idx, org in enumerate(orgs):
        name = (org.get("name") or "").strip()
        if not name:
            continue
        ig_handle, x_handle, website = classify(org.get("url"))
        artists.append({
            "id": idx,
            "name": name,
            "booth": (org.get("location") or "").strip() or None,
            "website": website,
            "x_handle": x_handle,
            "ig_handle": ig_handle,
            "desc": "",
        })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(artists, f, indent=2, ensure_ascii=False)

    total = len(artists)
    with_x = sum(1 for a in artists if a["x_handle"])
    with_ig = sum(1 for a in artists if a["ig_handle"])
    with_both = sum(1 for a in artists if a["x_handle"] and a["ig_handle"])
    with_website_only = sum(
        1 for a in artists if a["website"] and not a["x_handle"] and not a["ig_handle"]
    )
    with_neither = sum(
        1 for a in artists if not a["x_handle"] and not a["ig_handle"] and not a["website"]
    )
    print(f"Wrote {total} artists -> {args.out}")
    print(f"  with X handle: {with_x}")
    print(f"  with IG handle: {with_ig}")
    print(f"  with both: {with_both}")
    print(f"  website only (needs resolve_socials.py): {with_website_only}")
    print(f"  with nothing: {with_neither}")


if __name__ == "__main__":
    main()
