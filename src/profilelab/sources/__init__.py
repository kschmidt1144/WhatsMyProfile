"""Connector registry and contract.

A connector is a module exposing:

    SOURCE: str            # short slug, namespaces every attribute it emits
    TITLE:  str            # human name
    MODE:   str            # broadcast | ambient | broker | inference
    available() -> bool    # is this connector configured? (missing key => skip)
    fetch(force=False)     # download raw artifacts into data/raw/<SOURCE>/
    parse() -> Collected   # raw artifacts -> attributes/signals/identities/inferences

`fetch` writes immutable raw artifacts plus a `_manifest.json` recording where
each came from and its sha256, so any figure can be traced back to bytes.
`parse` must be pure with respect to the network: it reads only what `fetch`
already wrote, which is what makes the test suite runnable offline.

Shared helpers live in `base.py` — import them from there, not from here.
"""

from __future__ import annotations

from types import ModuleType

from .base import now, raw_dir, sha256, write_manifest  # re-exported for convenience
from . import cadbr, github
from .adprefs import amazon, google, linkedin, meta, x

__all__ = ["REGISTRY", "get", "now", "raw_dir", "sha256", "write_manifest"]

REGISTRY: dict[str, ModuleType] = {
    github.SOURCE: github,
    cadbr.SOURCE: cadbr,
    x.SOURCE: x,
    linkedin.SOURCE: linkedin,
    meta.SOURCE: meta,
    google.SOURCE: google,
    amazon.SOURCE: amazon,
}


def get(source: str) -> ModuleType:
    if source not in REGISTRY:
        known = ", ".join(sorted(REGISTRY)) or "(none)"
        raise KeyError(f"unknown source {source!r}; known: {known}")
    return REGISTRY[source]
