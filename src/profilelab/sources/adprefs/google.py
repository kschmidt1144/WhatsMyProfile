"""Google — My Ad Center topics, via Takeout.

Google shows the live version at myadcenter.google.com; the durable, parseable
version arrives through Takeout. Format and path are the least stable of the
five, so the candidate list is broad and the walker is tolerant.
"""

from __future__ import annotations

from pathlib import Path

from . import base
from .base import Claim

SOURCE = "google_ads"
TITLE = "Google My Ad Center topics (Takeout)"
MODE = base.MODE


def _parse(path: Path) -> list[Claim]:
    if path.suffix.casefold() == ".csv":
        return base.csv_topics(path, facet="interest")
    return base.json_topics(path, facet="interest")


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "takeout.google.com → deselect all → select 'My Ad Center'. "
        "(The live view is myadcenter.google.com → 'Your ad topics'.) "
        "Unpack into <exports>/google_ads/."
    ),
    candidates=(
        "My Ad Center/*.json",
        "My Ad Center/*.csv",
        "*Ad*Center*.json",
        "*Ad*Center*.csv",
        "Ads/*.json",
        "*ad*topics*.json",
    ),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
