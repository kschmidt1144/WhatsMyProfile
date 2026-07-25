"""LinkedIn — `Ad_Targeting.csv` and `Inferences.csv` from the data export.

Unusual among the five in that it mixes disclosed and inferred material in one
file: your job title is something you typed, your inferred seniority and
interests are not. The `disclosed` flag is set per column accordingly, which is
what makes this connector useful for measuring the inference gap rather than
just listing topics.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import base
from .base import Claim

SOURCE = "linkedin_ads"
TITLE = "LinkedIn ad targeting and inferences (data export)"
MODE = base.MODE

# Columns of Ad_Targeting.csv sourced from what the member typed into their
# profile. Everything else in that file is derived by LinkedIn.
_DISCLOSED_COLUMNS = {
    "company names", "degrees", "fields of study", "job titles", "titles",
    "member schools", "member skills", "profile locations", "language",
}

# Columns that are demographic rather than interest-shaped.
_DEMOGRAPHIC_COLUMNS = {
    "member age", "member gender", "job seniority", "years of experience",
    "company size", "location",
}


def _parse_targeting(path: Path) -> list[Claim]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    claims: list[Claim] = []
    for row in rows:
        for column, raw in row.items():
            if not column or not raw or not raw.strip():
                continue
            key = column.strip().casefold()
            facet = "demographic" if key in _DEMOGRAPHIC_COLUMNS else "interest"
            disclosed = key in _DISCLOSED_COLUMNS
            # LinkedIn packs multiple values into one cell, semicolon-separated.
            for value in raw.split(";"):
                value = value.strip()
                if not value:
                    continue
                # Interests are emitted bare so they can be compared against the
                # other platforms' topic strings — prefixing them with the column
                # name would make every cross-platform match fail. Demographics
                # keep their key, since "25-34" alone means nothing.
                topic = f"{key} = {value}" if facet == "demographic" else value
                claims.append(Claim(topic, facet, disclosed))
    return claims


def _parse_inferences(path: Path) -> list[Claim]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    claims: list[Claim] = []
    for row in rows:
        normalised = {(k or "").strip().casefold(): (v or "").strip() for k, v in row.items()}
        verdict = normalised.get("inference", "")
        # The file lists every inference LinkedIn considered, with a yes/no.
        # Only the affirmative ones are claims about you.
        if verdict.casefold() not in {"yes", "true"}:
            continue
        label = normalised.get("type of inference") or normalised.get("description")
        if label:
            claims.append(Claim(label, "demographic", disclosed=False))
    return claims


def _parse(path: Path) -> list[Claim]:
    name = path.name.casefold()
    if "inference" in name:
        return _parse_inferences(path)
    return _parse_targeting(path)


PLATFORM = base.Platform(
    source=SOURCE,
    title=TITLE,
    how_to=(
        "LinkedIn → Settings → Data privacy → Get a copy of your data → "
        "select the full archive. Unpack `Ad_Targeting.csv` and `Inferences.csv` "
        "into <exports>/linkedin_ads/."
    ),
    candidates=("Ad_Targeting.csv", "Inferences.csv", "*Ad_Targeting*.csv", "*Inferences*.csv"),
    parser=_parse,
)


def available() -> bool:
    return base.available(PLATFORM)


def fetch(force: bool = False):
    return base.fetch(PLATFORM, force)


def parse():
    return base.parse(PLATFORM)
