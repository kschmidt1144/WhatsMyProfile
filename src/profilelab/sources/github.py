"""GitHub — the broadcast half, plus a first demonstration of the inference gap.

Most of what this connector collects is disclosed by definition: a public
profile is public. The interesting part is the last step. GitHub has no
timezone field and never asks for one, but every public push is stamped in UTC,
and people do not push while asleep. The eight-hour trough in that histogram is
a sleep schedule, and its offset from 03:00 local is a timezone — a fact the
subject never entered anywhere, recovered from data they published on purpose.

That is the whole project in miniature: the profile is not what you filled in.

⚠️ **Known bias, measured on the first run.** The method assumes a chronotype:
that the middle of your quiet window is 03:00 local. For the repo author it
returned UTC-7 against a true UTC-4, because he sleeps roughly 02:00-10:00
rather than 23:00-07:00, and a three-hour-later sleep midpoint reads as three
hours further west. The failure is systematic and directional — night owls
resolve west, early risers east — so this connector's timezone claims are
recorded as `unverifiable` and must not be treated as ground truth. Fixing it
needs a population chronotype prior or a second, independent signal, not a
tuned constant. See docs/DESIGN.md, Finding 1.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

from ..config import env, subject
from ..model import Collected, Identity, Inference, Signal
from .base import now, raw_dir, sha256, write_manifest

SOURCE = "github"
TITLE = "GitHub public profile and activity"
MODE = "broadcast"

API = "https://api.github.com"
_TIMEOUT = 30

# The endpoints this connector reads, and the file each lands in.
_ENDPOINTS = {
    "user.json": "/users/{login}",
    "repos.json": "/users/{login}/repos?per_page=100&sort=pushed",
    "events.json": "/users/{login}/events/public?per_page=100",
}


def login() -> str | None:
    return env("WMP_GITHUB_LOGIN")


def available() -> bool:
    return login() is not None


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "profilelab (What's My Profile research lab)",
    }
    # Unauthenticated works at 60 req/hr, which is enough; a token buys 5000.
    token = env("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch(force: bool = False) -> list[Path]:
    who = login()
    if not who:
        raise RuntimeError("WMP_GITHUB_LOGIN is not set — see .env.example")

    out = raw_dir(SOURCE)
    written: list[Path] = []
    entries: list[dict] = []

    for filename, template in _ENDPOINTS.items():
        path = out / filename
        url = API + template.format(login=who)
        if path.exists() and not force:
            written.append(path)
            entries.append({"file": filename, "url": url, "sha256": sha256(path), "cached": True})
            continue

        response = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            hint = " (set GITHUB_TOKEN to raise the 60/hr limit)" if remaining == "0" else ""
            raise RuntimeError(f"GitHub rate-limited {url}{hint}")
        response.raise_for_status()

        path.write_text(json.dumps(response.json(), indent=2))
        written.append(path)
        entries.append({"file": filename, "url": url, "sha256": sha256(path), "cached": False})

    write_manifest(SOURCE, entries)
    return written


def infer_utc_offset(hour_counts: list[int]) -> tuple[int, float] | None:
    """Recover a UTC offset from a 24-bin histogram of activity by UTC hour.

    Finds the circular 8-hour window carrying the least activity — the sleep
    window — and reads its midpoint as 03:00 local time. Returns the offset in
    hours and a confidence in [0, 1], or None if there is nothing to go on.

    Confidence reflects two things that can each make the answer worthless: a
    trough that is not actually a trough (activity spread evenly across the
    day, as with bots or scheduled jobs) and too few events to have a shape at
    all. Both drive it toward zero rather than producing a false precision.

    It does **not** capture the dominant error, which is chronotype: the 03:00
    assumption is a prior about when people sleep, and it is wrong by hours for
    anyone who is not a median sleeper. Confidence here means "there is a real
    trough and enough data to see it", never "the offset is correct".
    """
    if len(hour_counts) != 24:
        raise ValueError(f"expected 24 hourly bins, got {len(hour_counts)}")
    if any(c < 0 for c in hour_counts):
        raise ValueError("counts must be non-negative")

    total = sum(hour_counts)
    if total == 0:
        return None

    window = 8
    sums = [sum(hour_counts[(start + i) % 24] for i in range(window)) for start in range(24)]
    quietest = min(range(24), key=lambda start: sums[start])

    # Midpoint of an 8-hour window starting at `quietest`, read as 03:00 local.
    midpoint_utc = (quietest + window / 2) % 24
    offset = round(3.0 - midpoint_utc)
    # Normalise into the real range of world offsets, [-12, +11].
    offset = ((offset + 12) % 24) - 12

    # A flat day gives the quiet window its uniform share (8/24) of events;
    # a real sleep trough gives it far less.
    expected = total * window / 24
    depth = 1.0 - (sums[quietest] / expected) if expected else 0.0
    sample = min(1.0, total / 50.0)
    confidence = max(0.0, min(1.0, depth)) * sample
    return offset, round(confidence, 3)


def _push_hours(events: list[dict]) -> Counter:
    hours: Counter = Counter()
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        stamp = event.get("created_at")
        if not stamp:
            continue
        hours[datetime.fromisoformat(stamp).hour] += 1
    return hours


def parse() -> Collected:
    out = raw_dir(SOURCE)
    missing = [name for name in _ENDPOINTS if not (out / name).exists()]
    if missing:
        raise RuntimeError(f"no raw {SOURCE} data ({', '.join(missing)}) — run `wmp refresh -s {SOURCE}` first")

    user = json.loads((out / "user.json").read_text())
    repos = json.loads((out / "repos.json").read_text())
    events = json.loads((out / "events.json").read_text())

    who = user.get("login", login() or "unknown")
    me = subject()
    ident = f"gh:{who}"
    seen = now()
    profile_url = f"{API}/users/{who}"
    collected = Collected()

    collected.identities.append(
        Identity(identity=ident, kind="handle", subject=me, linked_via="configured WMP_GITHUB_LOGIN")
    )

    def signal(attribute: str, value, *, evidence: str, numeric: float | None = None) -> None:
        if value is None or value == "":
            return  # an unset profile field is an absence, not a fact
        collected.signals.append(
            Signal(
                subject=me,
                identity=ident,
                source=SOURCE,
                attribute=attribute,
                value=str(value),
                value_num=numeric,
                observed_at=seen,
                evidence=evidence,
            )
        )

    # ── disclosed profile fields ─────────────────────────────────────────────
    for attribute, key in (
        ("github/login", "login"),
        ("github/name", "name"),
        ("github/bio", "bio"),
        ("github/company", "company"),
        ("github/location", "location"),
        ("github/blog", "blog"),
        ("github/email", "email"),
        ("github/created_at", "created_at"),
    ):
        signal(attribute, user.get(key), evidence=profile_url)
    signal("github/followers", user.get("followers"), evidence=profile_url, numeric=float(user.get("followers") or 0))
    signal(
        "github/public_repos",
        user.get("public_repos"),
        evidence=profile_url,
        numeric=float(user.get("public_repos") or 0),
    )

    # ── languages, weighted by how many public repos use them ────────────────
    languages = Counter(repo["language"] for repo in repos if repo.get("language"))
    repos_url = f"{API}/users/{who}/repos"
    for language, count in languages.most_common():
        signal("github/language", language, evidence=repos_url, numeric=float(count))

    # ── the activity histogram, and what it gives away ───────────────────────
    hours = _push_hours(events)
    events_url = f"{API}/users/{who}/events/public"
    for hour in sorted(hours):
        signal("github/push_hour_utc", hour, evidence=events_url, numeric=float(hours[hour]))

    guess = infer_utc_offset([hours.get(hour, 0) for hour in range(24)])
    if guess:
        offset, confidence = guess
        collected.inferences.append(
            Inference(
                subject=me,
                claim=f"timezone ≈ UTC{offset:+d}",
                inferred_by="github-activity",
                from_sources=SOURCE,
                # GitHub has no timezone field. This was never entered anywhere.
                disclosed=False,
                verdict="unverifiable",
                confidence=confidence,
                method=(
                    f"quietest 8h window in {sum(hours.values())} public push timestamps, "
                    "read as 03:00 local"
                ),
            )
        )

    return collected
