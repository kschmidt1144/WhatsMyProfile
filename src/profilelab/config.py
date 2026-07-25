"""Paths, environment, and the constants the whole lab measures against.

The `~/Repos` workspace has a stray `.env` at its root; a bare `load_dotenv()`
walks *up* the tree and swallows it, silently repointing credentials at another
project. So this repo's `.env` is loaded by explicit path, never by search.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
TIDY = DATA / "tidy"
WAREHOUSE = DATA / "warehouse.duckdb"
REPORT = ROOT / "report"
FIGURES = REPORT / "figures"

load_dotenv(ROOT / ".env", override=False)

# The population an anonymity set is measured against. log2(8.2e9) = 32.93, so
# ~33 bits of accumulated surprisal singles out one living human. This is the
# budget every surface in the lab is scored against.
WORLD_POPULATION = 8_200_000_000


def env(name: str, default: str | None = None) -> str | None:
    """Read a config value, treating blank as absent.

    `.env.example` ships every key present-but-empty, so an unfilled key must
    read as missing or connectors would try to authenticate with "".
    """
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def subject() -> str:
    """The person being profiled. Signals are attached to this label."""
    return env("WMP_SUBJECT", "me") or "me"


def ensure_dirs() -> None:
    for path in (DATA, RAW, TIDY, FIGURES):
        path.mkdir(parents=True, exist_ok=True)
