"""Meta (Facebook / Instagram) — the `ads_information/` tree of the DYI export.

Meta restructures this archive often enough that hard-coding a path is a
liability, so this matches several known filenames and falls back to the
tolerant JSON walker. It over-collects rather than risk reporting an empty
profile that looks like a clean one.
"""

from __future__ import annotations

from pathlib import Path

from . import base
from .base import Claim

SOURCE = "meta_ads"
TITLE = "Meta ad preferences and advertiser lists (Download Your Information)"
MODE = base.MODE


def _parse(path: Path) -> list[Claim]:
    name = path.name.casefold()
    # Files about *who targeted you* are facts about advertisers, not claims
    # about you, so they land in a different facet and produce no inference.
    if "advertiser" in name or "contact_list" in name:
        return base.json_topics(path, facet="advertiser")
    if "categor" in name or "audience" in name:
        return base.json_topics(path, facet="audience")
    return base.json_topics(path, facet="interest")


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "Facebook → Settings → Your information → Download your information → "
        "select JSON format and the 'Ads information' category. Unpack the "
        "`ads_information/` directory into <exports>/meta_ads/."
    ),
    candidates=(
        "ad_preferences.json",
        "ads_interests.json",
        "other_categories_used_to_reach_you.json",
        "advertisers_using_your_activity_or_information.json",
        "advertisers_who_uploaded_a_contact_list_with_your_information.json",
        "ads_information/*.json",
        "*ad*preference*.json",
    ),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
