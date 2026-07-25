"""X / Twitter — `personalization.js` from the account archive.

The richest of the five: X publishes inferred gender, inferred age range,
inferred languages, an interest list, and the advertisers who uploaded a list
you appeared on. None of it was entered by you.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import base
from .base import Claim

SOURCE = "x_ads"
TITLE = "X/Twitter ad personalization (account archive)"
MODE = base.MODE


def _parse(path: Path) -> list[Claim]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # The archive ships JSON wrapped in a JS assignment:
    #   window.YTD.personalization.part0 = [ ... ]
    start = text.find("[")
    payload = text[start:] if start >= 0 else text
    data = json.loads(payload)
    if isinstance(data, dict):
        data = [data]

    claims: list[Claim] = []
    for entry in data:
        p13n = entry.get("p13nData", entry) if isinstance(entry, dict) else {}
        demo = p13n.get("demographics") or {}

        gender = (demo.get("genderInfo") or {}).get("gender")
        if gender:
            claims.append(Claim(f"gender = {gender}", "demographic"))

        age_range = (demo.get("age") or {}).get("ageRange")
        if age_range:
            claims.append(Claim(f"age range = {age_range}", "demographic"))

        for lang in demo.get("languages") or []:
            name = lang.get("language") if isinstance(lang, dict) else lang
            if name:
                claims.append(Claim(f"language = {name}", "demographic"))

        inferred_age = (p13n.get("inferredAgeInfo") or {}).get("age") or []
        for value in inferred_age:
            claims.append(Claim(f"inferred age = {value}", "demographic"))

        interests_block = p13n.get("interests") or {}
        for interest in interests_block.get("interests") or []:
            name = interest.get("name") if isinstance(interest, dict) else interest
            # Interests the user has explicitly switched off are still recorded
            # by the platform; skip them so we measure the live profile.
            if name and not (isinstance(interest, dict) and interest.get("isDisabled")):
                claims.append(Claim(name, "interest"))

        for partner in interests_block.get("partnerInterests") or []:
            name = partner.get("name") if isinstance(partner, dict) else partner
            if name:
                claims.append(Claim(name, "interest"))

        audiences = interests_block.get("audienceAndAdvertisers") or {}
        for key in ("advertisers", "lookalikeAdvertisers"):
            for advertiser in audiences.get(key) or []:
                if isinstance(advertiser, str) and advertiser.strip():
                    claims.append(Claim(advertiser.strip(), "advertiser"))

        for show in interests_block.get("shows") or []:
            if isinstance(show, str) and show.strip():
                claims.append(Claim(show.strip(), "interest"))

    return claims


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "X → Settings → Your account → Download an archive of your data. "
        "Unpack it and copy `data/personalization.js` into "
        "<exports>/x_ads/ (or drop the whole archive there)."
    ),
    candidates=("personalization.js", "personalization.json"),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
