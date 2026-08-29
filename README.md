# FAN EXPO Canada 2026 Artist Alley — ranked by social following

A single-page ranked list of all artists in the [FAN EXPO Canada 2026 Artist Alley](https://fanexpohq.com/fanexpocanada/artist-alley/), sorted by a combined Instagram + Twitter/X follower score.

## How it works

| step | what | how |
| --- | --- | --- |
| 1 | parse | `parse.py` reads a saved copy of FAN EXPO's [exhibitor directory](https://fanexpohq.com/fanexpocanada/exhibitor-directory/) page. The page ships its full exhibitor data as JSON in `window.__REDUX_STORE__`; we pull the "Artist Alley" category out of `sponsorsCategories`, which gives each exhibitor a name, booth, and a single external URL. That URL is classified as a direct Instagram handle, a direct X handle, or (most commonly) just a `website` — a personal site, carrd, Linktree, Etsy, ArtStation, etc. |
| 2 | resolve | `resolve_socials.py` fetches each `website`-only artist's page once and regexes out any `instagram.com/...` or `twitter.com`/`x.com/...` links it finds (e.g. header/footer social icons on a carrd or personal site), filling in `ig_handle`/`x_handle` where possible. |
| 3 | scrape | `scrape.py` fetches each artist's IG `og:description` meta tag for follower count ("29K Followers, …"), and pulls X follower count from `syndication.twitter.com`'s embed page (the only login-free way that still returns the number). |
| 4 | re-scrape X | `rescrape_x.py` retries any X handles that got rate-limited (HTTP 429) the first time, one at a time with delays. |
| 5 | build | `build.py` injects the resulting JSON into `template.html` at the `__DATA__` placeholder and writes the final `index.html` (root) + `dist/index.html` (preview). |

FAN EXPO's exhibitor directory doesn't expose per-artist social links directly the way Anime Expo's list did — most artists only list one outbound URL, and it's frequently a carrd/Linktree/personal site rather than a social profile. The resolve step exists to bridge that gap; artists whose linked site doesn't itself link out to IG/X (e.g. an Etsy or ArtStation shop) end up with a `website` link on the page instead of a follower score.

## Scoring

```
score = max(IG followers, X followers)
```

Artists with only one platform score on whichever they have. Artists with private / suspended / empty profiles get no follower number for that platform. Artists with no resolvable IG/X handle at all show their website link and sort last.

## Running the steps again

```bash
python3 parse.py "/path/to/Exhibitor Directory - FAN EXPO Canada.htm"   # → artists.json
python3 resolve_socials.py --workers 8 --resume                         # → artists_resolved.json
python3 scrape.py --in artists_resolved.json --workers 6 --resume       # → artists_enriched.json
python3 rescrape_x.py       # patch up the 429'd X handles
python3 build.py            # → index.html + dist/index.html
```

To get the input HTML for step 1: open the [exhibitor directory](https://fanexpohq.com/fanexpocanada/exhibitor-directory/) in a browser, filter to (or just leave on "All" — the parser filters by category itself) the categories you want, let the page fully load, then save it (View Source, or Save Page As → Webpage, Complete).
