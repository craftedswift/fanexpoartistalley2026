# Handoff: finishing this on your own machine

Everything up through parsing the real FAN EXPO Canada 2026 Artist Alley
roster is done and pushed to branch `claude/ax2026-artists-base-xb2reu`.
What's left (resolving social links + fetching follower counts) needs a
network connection to Instagram/Twitter/X, which this cloud sandbox
doesn't have — so it needs to run from your own machine.

## 1. Get the code

```bash
git clone https://github.com/craftedswift/fanexpoartistalley2026.git
cd fanexpoartistalley2026
git checkout claude/ax2026-artists-base-xb2reu
```

If you'd rather work on `main`, merge that branch in first.

## 2. Install Claude Code (optional, but this is written for it)

```bash
npm install -g @anthropic-ai/claude-code
```

Then from inside the repo directory, just run:

```bash
claude
```

It'll pick up `README.md` and the scripts automatically. If you'd rather
run the pipeline yourself without Claude, skip to step 4 — none of this
needs an AI to execute, Claude is just there to watch the output, debug
any script that trips up, and adjust things as needed.

## 3. Python setup

```bash
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install requests
```

(`beautifulsoup4` is no longer needed — `parse.py` now reads FAN EXPO's
embedded JSON directly instead of scraping HTML tags. If you re-run
`parse.py` you don't need to reinstall it, but it's still in the old
`requirements` if your environment references one.)

## 4. Run the pipeline

`artists.json` in the repo already has the real 478-artist FAN EXPO
Canada 2026 Artist Alley list (parsed from the exhibitor directory export).
You only need to re-run `parse.py` if FAN EXPO's list changes and you
grab a fresh export. Otherwise, start at step 2:

```bash
# 1. (only if re-parsing) save a fresh copy of
#    https://fanexpohq.com/fanexpocanada/exhibitor-directory/
#    (View Source, or Save Page As -> Webpage, Complete), then:
python3 parse.py "/path/to/Exhibitor Directory - FAN EXPO Canada.htm"

# 2. follow each artist's website/carrd/Linktree link to find IG/X handles
python3 resolve_socials.py --workers 8 --resume

# 3. fetch follower counts for every resolved handle
python3 scrape.py --in artists_resolved.json --workers 6 --resume

# 4. retry any X/Twitter handles that got rate-limited (HTTP 429)
python3 rescrape_x.py

# 5. build the site
python3 build.py
```

`resolve_socials.py` and `scrape.py` both support `--resume`, so if a run
gets interrupted (rate limits, network hiccup, closing your laptop),
just re-run the same command — it picks up where it left off using the
`id` field, skipping anything already in the output file.

Expect `scrape.py` to take a while: it's fetching hundreds of Instagram
and Twitter/X pages, throttled with small random delays to avoid getting
blocked. `rescrape_x.py` in particular is deliberately slow (steady pace
+ cooldowns) since X's syndication endpoint rate-limits aggressively.

## 5. Check the result

```bash
python3 -m http.server 8000 --directory dist
```

Open `http://localhost:8000` and confirm artists show follower counts
and sort correctly. `index.html` at the repo root is the same file and
is what GitHub Pages (or wherever you deploy) will serve.

## 6. Push it

```bash
git add artists_resolved.json artists_enriched.json index.html
git commit -m "Populate FAN EXPO Canada 2026 Artist Alley follower data"
git push
```

(`dist/` is gitignored on purpose — only the root `index.html` is deployed.)

## Known gaps to watch for

- **Artists with no resolvable social handle.** ~90 of the 478 link
  directly to a shop page (Etsy, Shopify, ArtStation, Toyhou.se) that
  `resolve_socials.py` intentionally skips (see `SKIP_HOSTS` in that
  file) since those pages rarely link back out to IG/X. Those artists
  will show their website link on the site instead of a follower score
  — that's expected, not a bug.
- **Malformed URLs in FAN EXPO's own data.** A couple of entries had
  typos like `https://www.Instagram` with no handle at all — `parse.py`
  already handles the common `Instagram/handle` (missing `.com`) case,
  but if you spot more after a fresh export, check `classify()` in
  `parse.py`.
- **Instagram/X may start blocking scrape requests.** If `scrape.py`
  starts returning a wall of `http:429` or `no-og-desc` errors, slow
  down `--workers` and let `rescrape_x.py`'s cooldown logic do its job
  rather than hammering retries.
