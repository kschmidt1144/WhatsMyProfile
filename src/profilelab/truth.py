"""Ground truth — the subject's own verdict on what was inferred about them.

Without this, `verdict` is `unverifiable` forever and the inference gap stays a
theory. With it, every derived claim becomes scoreable: was it right, and had
the subject ever disclosed it?

⚠️ **This is the most sensitive artifact in the project, and it is deliberately
kept apart from everything else.**

A platform guessing you are moving house is speculation. You confirming it is
fact. The verdict store therefore contains, by construction, a *better* dossier
than the one under study — which is the ethical tension recorded as an open
question in docs/DESIGN.md, and the reason for these three constraints:

1. **Its own file**, `data/truth/verdicts.json`, not the warehouse. Deleting
   your ground truth is `rm` on one path, and `wmp refresh` never touches it.
2. **Verdicts only.** A correct/incorrect/unverifiable trit plus an optional
   note. The store never invites free-text disclosure of *what is actually
   true* — only a judgement on a claim someone else already made.
3. **Never derived, never inferred.** Nothing writes here except the subject
   answering a direct question.

Verdicts survive `wmp refresh` because they live outside the connector
pipeline and are joined onto the `inferences` table at warehouse-build time —
the same shape the World Economy Lab uses for margin notes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA
from .model import VERDICTS

STORE = DATA / "truth" / "verdicts.json"

_HEADER = (
    "The subject's own verdicts on claims inferred about them. This file is "
    "personal data of a higher order than the inferences it scores — never "
    "commit it, never share it, delete it freely. See src/profilelab/truth.py."
)


def claim_key(source: str, claim: str) -> str:
    """Stable identity for a claim, so a verdict survives re-collection.

    Keyed on source plus normalised claim text. If a platform renames a topic
    the verdict orphans rather than silently attaching to the wrong claim —
    `orphans()` reports those instead of hiding them.
    """
    return f"{source.strip().casefold()}::{' '.join(claim.split()).casefold()}"


def load() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    try:
        payload = json.loads(STORE.read_text())
    except json.JSONDecodeError:
        return {}
    return payload.get("verdicts", {})


def save(verdicts: dict[str, dict]) -> Path:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(
        json.dumps({"version": 1, "note": _HEADER, "verdicts": verdicts}, indent=2, sort_keys=True)
    )
    return STORE


def record(source: str, claim: str, verdict: str, note: str | None = None) -> str:
    """Store one verdict. Returns the key it was filed under."""
    if verdict not in VERDICTS:
        raise ValueError(f"unknown verdict {verdict!r}; expected one of {sorted(VERDICTS)}")
    verdicts = load()
    key = claim_key(source, claim)
    verdicts[key] = {
        "source": source,
        "claim": claim,
        "verdict": verdict,
        "note": note,
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save(verdicts)
    return key


def verdict_for(source: str, claim: str) -> str | None:
    entry = load().get(claim_key(source, claim))
    return entry["verdict"] if entry else None


def orphans(known: set[str]) -> list[dict]:
    """Verdicts whose claim no longer appears in the warehouse.

    Usually means a platform reworded or dropped a topic. Surfaced rather than
    silently carried, because a stale verdict is a wrong verdict.
    """
    return [entry for key, entry in load().items() if key not in known]


def forget(source: str, claim: str) -> bool:
    verdicts = load()
    key = claim_key(source, claim)
    if key not in verdicts:
        return False
    del verdicts[key]
    save(verdicts)
    return True


def clear() -> int:
    """Delete every recorded verdict. Returns how many were removed."""
    count = len(load())
    if STORE.exists():
        STORE.unlink()
    return count
