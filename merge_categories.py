"""Merge manually-classified product categories into artists_enriched.json.

Categories are inferred from each artist's website content (title, meta
description, visible text - see fetch_site_text.py) since FAN EXPO's own
exhibitor data has no product-type field (see parse.py). Artists with no
fetchable site text, or whose site gave no signal, get an empty list.

Usage:
    python3 merge_categories.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent

with open(ROOT / "artists_enriched.json", encoding="utf-8") as f:
    artists = json.load(f)

with open(ROOT / "categories_manual.json", encoding="utf-8") as f:
    cats = {int(k): v for k, v in json.load(f).items()}

for a in artists:
    a["categories"] = cats.get(a["id"], [])

with open(ROOT / "artists_enriched.json", "w", encoding="utf-8") as f:
    json.dump(artists, f, indent=2, ensure_ascii=False)

tagged = sum(1 for a in artists if a["categories"])
print(f"Tagged {tagged}/{len(artists)} artists with categories")
