"""Inject artists_enriched.json into index.html's __DATA__ placeholder."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
SRC_HTML = ROOT / "template.html"
DATA = ROOT / "artists_enriched.json"
# Two outputs: dist/ for the local preview server, and ./index.html at the
# repo root for GitHub Pages.
OUT_HTML = ROOT / "dist" / "index.html"
OUT_ROOT = ROOT / "index.html"


def main():
    with open(SRC_HTML) as f:
        html = f.read()
    with open(DATA) as f:
        artists = json.load(f)

    # slim down each record to only what the page needs
    slim = []
    for a in artists:
        # drop the AX placeholder "Artist Directory" entry
        if "Artist Directory" in (a.get("name") or ""):
            continue
        slim.append({
            "id": a["id"],
            "name": a["name"],
            "booth": a.get("booth"),
            "website": a.get("website"),
            "desc": (a.get("desc") or "").strip()[:280],
            "x_handle": a.get("x_handle"),
            "ig_handle": a.get("ig_handle"),
            "ig_followers": a.get("ig_followers"),
            "x_followers": a.get("x_followers"),
            "ig_profile_pic": a.get("ig_profile_pic"),
            "x_profile_pic": a.get("x_profile_pic"),
            "x_name": a.get("x_name"),
        })

    js = json.dumps(slim, ensure_ascii=False)
    # protect against </script> sneaking into bio text
    js = js.replace("</script>", "<\\/script>")
    out_html = html.replace("__DATA__", js)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_HTML, OUT_ROOT):
        with open(path, "w") as f:
            f.write(out_html)
        print(f"Wrote {path} ({len(out_html)/1024:.1f} KB, {len(slim)} artists)")


if __name__ == "__main__":
    main()
