"""Parse the AX 2026 artist alley HTML into a clean JSON.

Trust URL hosts, not the visible icon images (the source HTML's icons are
mis-paired with their hrefs).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

SRC = "/Users/shizukaziye/Downloads/AX 2026 ARTIST ALLEY LIST - Anime Expo.html"
OUT = "/Users/shizukaziye/Documents/ax2026-artists/artists.json"


def handle_from_url(url: str, host_predicate) -> str | None:
    try:
        p = urlparse(url)
    except Exception:
        return None
    if not host_predicate(p.netloc.lower()):
        return None
    parts = [s for s in p.path.split("/") if s]
    if not parts:
        return None
    handle = parts[0].strip().lstrip("@")
    return handle or None


def is_x(host: str) -> bool:
    return host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}


def is_ig(host: str) -> bool:
    return host in {"instagram.com", "www.instagram.com", "m.instagram.com"}


def is_social_other(host: str) -> bool:
    return any(s in host for s in ("tiktok.com", "facebook.com", "youtube.com", "youtu.be", "bsky"))


def main():
    with open(SRC) as f:
        soup = BeautifulSoup(f, "html.parser")

    artists = []
    skip_keywords = {"animeexpo"}  # the page header has the AX official socials

    for idx, item in enumerate(soup.select("div.inner-item")):
        title_div = item.select_one("div.title")
        if not title_div:
            continue
        name_a = title_div.select_one("a.pjs-sig-name")
        name = (name_a.get_text(strip=True) if name_a else "").strip()
        if not name:
            continue

        x_handle = None
        ig_handle = None
        other_links = []
        primary_link = name_a["href"] if name_a and name_a.has_attr("href") else None

        for a in item.select("a"):
            href = a.get("href", "").strip()
            if not href:
                continue
            h = handle_from_url(href, is_x)
            if h and h.lower() not in skip_keywords and not x_handle:
                x_handle = h
                continue
            h = handle_from_url(href, is_ig)
            if h and h.lower() not in skip_keywords and not ig_handle:
                ig_handle = h
                continue

        # booth
        booth = None
        channel = item.select_one("div.channel")
        if channel:
            m = re.search(r"Table:\s*(.+)", channel.get_text(" ", strip=True))
            if m:
                booth = m.group(1).strip()

        # website
        website = None
        start = item.select_one("div.start a")
        if start and start.has_attr("href"):
            website = start["href"].strip()

        # description
        desc = item.select_one("div.desc")
        desc_text = desc.get_text(" ", strip=True) if desc else ""

        artists.append({
            "id": idx,
            "name": name,
            "booth": booth,
            "website": website,
            "x_handle": x_handle,
            "ig_handle": ig_handle,
            "desc": desc_text,
        })

    with open(OUT, "w") as f:
        json.dump(artists, f, indent=2, ensure_ascii=False)

    total = len(artists)
    with_x = sum(1 for a in artists if a["x_handle"])
    with_ig = sum(1 for a in artists if a["ig_handle"])
    with_both = sum(1 for a in artists if a["x_handle"] and a["ig_handle"])
    with_neither = sum(1 for a in artists if not a["x_handle"] and not a["ig_handle"])
    print(f"Wrote {total} artists -> {OUT}")
    print(f"  with X handle: {with_x}")
    print(f"  with IG handle: {with_ig}")
    print(f"  with both: {with_both}")
    print(f"  with neither: {with_neither}")


if __name__ == "__main__":
    main()
