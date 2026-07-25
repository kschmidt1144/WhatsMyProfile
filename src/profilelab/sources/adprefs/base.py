"""Shared machinery for ad-preference connectors.

These platforms will tell you their inferred profile of you — it is the closest
thing to a free confession the surveillance economy offers. But only to you,
behind a login, as a bulk archive. There is no public API, and scraping an
authenticated session would be brittle and against terms.

So these are **export-file connectors**. You request the archive, unpack it
somewhere under the exports directory, and the connector parses it. `fetch()`
touches no network; it locates the file and records its hash for provenance.

⚠️ **Export formats drift constantly.** Paths get renamed, JSON gets restructured,
CSV columns come and go. Every platform therefore declares a list of *candidate*
patterns rather than one path, parsers are defensive about missing keys, and
`wmp exports` reports exactly what was searched for and what was found. A
connector that finds nothing says so rather than silently reporting an empty
profile — the difference between "no data" and "no interests inferred" matters.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ...config import DATA, env, subject
from ...model import Collected, Identity, Inference, Signal
from ..base import now, raw_dir, sha256, write_manifest

MODE = "inference"

# Facets of a platform's profile of you. `advertiser` is a fact about who holds
# your data, not a claim about you, so it becomes a signal but not an inference.
FACETS = {
    "interest": ("adprefs/interest", True),
    "demographic": ("adprefs/demographic", True),
    "audience": ("adprefs/audience", True),
    "advertiser": ("adprefs/advertiser", False),
}


@dataclass(frozen=True)
class Claim:
    """One thing a platform asserts about you."""

    topic: str
    facet: str = "interest"
    # Did the subject state this themselves? Most ad-preference data is derived,
    # but a LinkedIn job title is something you typed in.
    disclosed: bool = False


@dataclass(frozen=True)
class Platform:
    source: str
    title: str
    # Where to get the export, shown by `wmp exports`.
    how_to: str
    # Glob patterns, tried in order, relative to the export search root.
    candidates: tuple[str, ...]
    parser: Callable[[Path], list[Claim]]


def exports_root() -> Path:
    """Where unpacked platform archives live. Gitignored; override with WMP_EXPORTS_DIR."""
    override = env("WMP_EXPORTS_DIR")
    return Path(override).expanduser() if override else DATA / "exports"


def find_files(platform: Platform) -> list[Path]:
    """Locate a platform's export files, forgivingly.

    Searches a per-platform subdirectory if one exists, otherwise the whole
    exports tree — so an archive unpacked anywhere sensible is still found.
    """
    root = exports_root()
    if not root.exists():
        return []
    scoped = root / platform.source
    base = scoped if scoped.exists() else root
    found: list[Path] = []
    for pattern in platform.candidates:
        found.extend(sorted(p for p in base.rglob(pattern) if p.is_file()))
    # Preserve candidate order, drop duplicates.
    seen, unique = set(), []
    for path in found:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def available(platform: Platform) -> bool:
    return bool(find_files(platform))


def fetch(platform: Platform, force: bool = False) -> list[Path]:
    """No network. Verify the export is present and record its provenance."""
    files = find_files(platform)
    if not files:
        raise RuntimeError(
            f"no {platform.source} export found under {exports_root()} — "
            f"looked for {', '.join(platform.candidates)}. See `wmp exports`."
        )
    write_manifest(
        platform.source,
        [{"file": str(p), "url": "local export", "sha256": sha256(p)} for p in files],
    )
    return files


def parse(platform: Platform) -> Collected:
    files = find_files(platform)
    if not files:
        raise RuntimeError(f"no {platform.source} export found — run `wmp exports` for instructions")

    me = subject()
    ident = f"{platform.source}:account"
    seen = now()
    collected = Collected()
    collected.identities.append(
        Identity(identity=ident, kind="account", subject=me, linked_via=f"{platform.source} data export")
    )

    claims: list[Claim] = []
    for path in files:
        try:
            claims.extend(platform.parser(path))
        except Exception as exc:  # noqa: BLE001 — a drifted format must not kill the run
            raise RuntimeError(f"could not parse {path.name}: {type(exc).__name__}: {exc}") from exc

    # Deduplicate: platforms repeat topics across files in the same archive.
    unique: dict[tuple[str, str], Claim] = {}
    for claim in claims:
        unique.setdefault((claim.facet, claim.topic.strip().casefold()), claim)

    for claim in unique.values():
        attribute, is_inference = FACETS.get(claim.facet, FACETS["interest"])
        evidence = f"{platform.source} data export"
        collected.signals.append(
            Signal(
                subject=me,
                identity=ident,
                source=platform.source,
                attribute=attribute,
                value=claim.topic,
                observed_at=seen,
                evidence=evidence,
            )
        )
        if is_inference:
            collected.inferences.append(
                Inference(
                    subject=me,
                    claim=f"{claim.facet}: {claim.topic}",
                    inferred_by=platform.source,
                    from_sources=platform.source,
                    disclosed=claim.disclosed,
                    # The platform asserts it; whether it is true is a separate
                    # question this lab cannot answer without ground truth.
                    verdict="unverifiable",
                    # It reached an ad-targeting system, so it is operative by
                    # construction — regardless of whether it is accurate.
                    effect="observed",
                    confidence=0.5,
                    method=f"declared by {platform.source} in its own ad-preference export",
                )
            )
    return collected


# ── tolerant parsers for formats that drift ──────────────────────────────────

_TOPIC_KEYS = {"name", "topic", "interest", "category", "audience", "advertiser", "title", "value"}


def json_topics(path: Path, facet: str = "interest") -> list[Claim]:
    """Walk arbitrary JSON and pull out topic-shaped strings.

    Used where a platform's schema is unstable enough that hard-coding a path
    would break on the next export. Over-collects rather than under-collects;
    the alternative is silently reporting an empty profile.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []

    out: list[Claim] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key.casefold() in _TOPIC_KEYS and value.strip():
                    out.append(Claim(value.strip(), facet))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str) and item.strip():
                    out.append(Claim(item.strip(), facet))
                else:
                    walk(item)

    walk(data)
    return out


def csv_topics(path: Path, facet: str = "audience", column: int = 0) -> list[Claim]:
    """Pull one column out of a CSV export, skipping a header row if present."""
    out: list[Claim] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return out
    start = 1 if rows and rows[0] and not rows[0][column].strip().startswith("http") else 0
    for row in rows[start:]:
        if len(row) > column and row[column].strip():
            out.append(Claim(row[column].strip(), facet))
    return out
