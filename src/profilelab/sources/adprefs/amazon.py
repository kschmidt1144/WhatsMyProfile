"""Amazon — advertising audience membership, via Request My Data.

Amazon reports the audience segments you were placed in rather than topic-style
interests, including third-party audiences it bought you into. That makes it the
best of the five for seeing yourself as an inventory item.
"""

from __future__ import annotations

from pathlib import Path

from . import base
from .base import Claim

SOURCE = "amazon_ads"
TITLE = "Amazon advertising audiences (Request My Data)"
MODE = base.MODE


def _parse(path: Path) -> list[Claim]:
    name = path.name.casefold()
    facet = "advertiser" if "advertiser" in name and "audience" not in name else "audience"
    if path.suffix.casefold() == ".csv":
        return base.csv_topics(path, facet=facet)
    return base.json_topics(path, facet=facet)


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "amazon.com → Account → Data Privacy → Request Your Information → "
        "'Advertising'. Unpack the `Advertising.*` files into <exports>/amazon_ads/."
    ),
    candidates=(
        "Advertising.AdvertiserAudiences.csv",
        "Advertising.AmazonAudiences.csv",
        "Advertising.3PAudiences.csv",
        "Advertising*/*.csv",
        "Advertising*.csv",
    ),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
