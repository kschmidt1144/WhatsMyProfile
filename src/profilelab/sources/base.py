"""Helpers every connector uses.

Separate from `sources/__init__.py` on purpose: the package `__init__` imports
the connector modules to build the registry, so anything a connector imports
has to live somewhere the `__init__` is not still mid-import.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import RAW


def raw_dir(source: str) -> Path:
    path = RAW / source
    path.mkdir(parents=True, exist_ok=True)
    return path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(source: str, entries: list[dict]) -> Path:
    """Record provenance for a fetch: what was downloaded, from where, and its hash.

    Every figure in this project must be traceable back to bytes; this is where
    that chain starts.
    """
    path = raw_dir(source) / "_manifest.json"
    path.write_text(json.dumps({"source": source, "fetched_at": now(), "files": entries}, indent=2))
    return path
