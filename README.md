# AX 2026 Artist Alley — ranked by social following

A single-page ranked list of all artists in the [Anime Expo 2026 Artist Alley](https://www.anime-expo.org/ax2026aalist/), sorted by a combined Instagram + Twitter/X follower score.

Live: https://shizukaziye.github.io/ax2026-artists/

## How it works

| step | what | how |
| --- | --- | --- |
| 1 | parse | `parse.py` reads the AX HTML list and pulls name, booth, X handle, IG handle, website, bio for each `div.inner-item`. It trusts the URL host over the icon image (the source HTML mis-pairs icons with hrefs). |
| 2 | scrape | `scrape.py` fetches each artist's IG `og:description` meta tag for follower count ("29K Followers, …"), and pulls X follower count from `syndication.twitter.com`'s embed page (the only login-free way that still returns the number). |
| 3 | re-scrape X | `rescrape_x.py` retries any X handles that got rate-limited (HTTP 429) the first time, one at a time with 4–20 s delays. |
| 4 | build | `build.py` injects the resulting JSON into `template.html` at the `__DATA__` placeholder and writes the final `index.html` (root) + `dist/index.html` (preview). |

## Scoring

```
score = max(IG followers, X followers)
```

Artists with only one platform score on whichever they have. Artists with private / suspended / empty profiles get no follower number for that platform.

## Running the steps again

```bash
python3 parse.py            # → artists.json
python3 scrape.py --workers 6 --resume   # → artists_enriched.json
python3 rescrape_x.py       # patch up the 429'd X handles
python3 build.py            # → index.html + dist/index.html
```
