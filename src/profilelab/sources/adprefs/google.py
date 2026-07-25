"""Google — My Ad Center topics and brands.

⚠️ **Takeout is the wrong route here.** Its "My Ad Center" export contains
*activity records* — "Blocked an ad from", "Chose to see fewer ads from",
"Liked an ad from" — which describe your actions on ads, not Google's inferred
profile of you. The topic list we actually want is only rendered in the live UI
at myadcenter.google.com and has no export button.

So this connector reads a small JSON capture taken from that UI. `wmp exports`
prints the snippet to paste into DevTools; the page lists each topic followed by
"Fewer like this" / "More like this", which is what the extraction keys on.

Two facets: `topics` are interests Google attributes to you, `brands` are
advertisers whose ads you have been shown — a fact about them, so those become
signals rather than inferences.
"""

from __future__ import annotations

from pathlib import Path

from . import base
from .base import Claim

SOURCE = "google_ads"
TITLE = "Google My Ad Center topics (Takeout)"
MODE = base.MODE


_EXTRACTION_JS = """
// Run on myadcenter.google.com/customize?ctb=topics&ctf=yours (and ctb=brands)
(() => {
  const lines = document.body.innerText.split('\\n').map(s => s.trim());
  const out = [];
  for (let i = 0; i < lines.length - 1; i++)
    if (lines[i + 1] === 'Fewer like this' && lines[i]) out.push(lines[i]);
  return JSON.stringify({topics: [...new Set(out)]}, null, 2);
})()
"""


def _parse(path: Path) -> list[Claim]:
    # Brands are advertisers who reached you, not claims about who you are.
    facet = "advertiser" if "brand" in path.name.casefold() else "interest"
    if path.suffix.casefold() == ".csv":
        return base.csv_topics(path, facet=facet)
    return base.json_topics(path, facet=facet)


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "Google has no export for this — Takeout's 'My Ad Center' holds only your "
        "actions on ads, not its topic list. Instead open "
        "myadcenter.google.com/customize?ctb=topics&ctf=yours (then ctb=brands), "
        "scroll to the bottom to load everything, and run the extraction snippet "
        "in DevTools. Save as my-ad-center-topics.json / -brands.json in "
        "<exports>/google_ads/. Snippet: profilelab.sources.adprefs.google._EXTRACTION_JS"
    ),
    candidates=(
        "my-ad-center-*.json",
        "My Ad Center/*.json",
        "My Ad Center/*.csv",
        "*Ad*Center*.json",
        "*Ad*Center*.csv",
        "*ad*topics*.json",
        "*ad*brands*.json",
    ),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
