"""California Data Broker Registry — the industry's own directory of itself.

California's Delete Act requires any company meeting the data-broker definition
to register annually with the CPPA and disclose what it collects, who it sells
to, and how it handled access requests. The result is a public CSV naming
hundreds of companies in the business of trading personal information, each
with a contact address and a data-subject-request URL.

For "who is collecting it", this is the highest-yield source in the project:
one download names more collectors than any amount of letter-writing would,
and needs no legal standing to obtain.

Two things it is **not**:

1. **Not a claim that any of them holds your data.** A registration says a
   company brokers personal information and is reachable here. Whether they
   hold a record on *you* is unknown until a subject-access request comes back —
   `Holder.confirmed` marks that difference.
2. **Not a complete census.** Registration is self-executing and enforcement is
   thin; EFF and Privacy Rights Clearinghouse both found hundreds of brokers
   registered in one state and not others. Absent from this list means
   unregistered here, not absent from the industry.

The disclosures are the companies' own, filed under penalty of the statute —
useful precisely because they are self-incriminating rather than observed.
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests

from ..model import Collected, Holder
from .base import raw_dir, sha256, write_manifest

SOURCE = "cadbr"
TITLE = "California Data Broker Registry (CPPA)"
MODE = "broker"

REGISTRY_URL = "https://cppa.ca.gov/data_broker_registry/registry.csv"
_TIMEOUT = 120

# Column headers are long, contain curly apostrophes, and get reworded between
# filing years — so every lookup is a case-folded substring match on a
# distinctive fragment rather than an exact key.
_FIELDS = {
    "name": "data broker name",
    "website": "primary website:",
    "contact": "primary contact email",
    "dsar": "details on how",
    "country": "data broker country",
}

# (label, distinctive fragment) for the self-reported sensitive categories.
_COLLECTS = (
    ("minors", "personal information of minors"),
    ("account logins", "account logins"),
    ("government ID", "government"),
    ("citizenship/immigration", "citizenship"),
    ("union membership", "union membership"),
    ("sexual orientation", "sexual orientation"),
    ("gender identity", "gender identity"),
    ("biometric", "biometric"),
    ("precise geolocation", "precise geolocation"),
    ("reproductive health", "reproductive health"),
)

_SELLS_TO = (
    ("foreign actor", "foreign actor"),
    ("federal government", "federal government"),
    ("state governments", "other state governments"),
    ("law enforcement", "law enforcement"),
    ("GenAI developer", "genai"),
)


def available() -> bool:
    return True  # public download, no credentials


def _find(columns: list[str], fragment: str) -> str | None:
    needle = fragment.casefold()
    for column in columns:
        if needle in (column or "").casefold():
            return column
    return None


def _num(value: str | None) -> int | None:
    try:
        return int(str(value or "").replace(",", "").strip())
    except ValueError:
        return None


def fetch(force: bool = False) -> list[Path]:
    out = raw_dir(SOURCE)
    path = out / "registry.csv"
    if not path.exists() or force:
        response = requests.get(
            REGISTRY_URL,
            timeout=_TIMEOUT,
            headers={"User-Agent": "profilelab (What's My Profile research lab)"},
        )
        response.raise_for_status()
        path.write_bytes(response.content)
    write_manifest(SOURCE, [{"file": path.name, "url": REGISTRY_URL, "sha256": sha256(path)}])
    return [path]


def parse() -> Collected:
    path = raw_dir(SOURCE) / "registry.csv"
    if not path.exists():
        raise RuntimeError(f"no registry downloaded — run `wmp refresh -s {SOURCE}`")

    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return Collected()

    columns = list(rows[0].keys())
    resolved = {key: _find(columns, frag) for key, frag in _FIELDS.items()}
    if not resolved["name"]:
        raise RuntimeError("registry CSV has no recognisable name column — schema changed")

    collects_cols = [(label, _find(columns, frag)) for label, frag in _COLLECTS]
    sells_cols = [(label, _find(columns, frag)) for label, frag in _SELLS_TO]
    know_total = _find(columns, "requests to know what personal information is being collected - total requests received")
    know_denied = _find(columns, "is being collected - total requests received - denied")

    def yes(row: dict, column: str | None) -> bool:
        return bool(column) and str(row.get(column, "")).strip().casefold() == "yes"

    collected = Collected()
    for row in rows:
        name = (row.get(resolved["name"]) or "").strip()
        if not name:
            continue
        collected.holders.append(
            Holder(
                holder=name,
                kind="broker",
                source=SOURCE,
                website=(row.get(resolved["website"]) or "").strip() if resolved["website"] else "",
                contact=(row.get(resolved["contact"]) or "").strip() if resolved["contact"] else "",
                dsar_url=(row.get(resolved["dsar"]) or "").strip() if resolved["dsar"] else "",
                country=(row.get(resolved["country"]) or "").strip() if resolved["country"] else "",
                collects=", ".join(label for label, col in collects_cols if yes(row, col)),
                sells_to=", ".join(label for label, col in sells_cols if yes(row, col)),
                know_requests=_num(row.get(know_total)) if know_total else None,
                know_denied=_num(row.get(know_denied)) if know_denied else None,
                # Registration proves they broker data, not that they hold yours.
                confirmed=False,
                evidence=REGISTRY_URL,
            )
        )
    return collected
