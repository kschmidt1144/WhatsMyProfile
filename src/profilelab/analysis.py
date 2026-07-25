"""Turning collected signals into the numbers the project is about.

Three corrections from the research pass are enforced here rather than left to
the reader (see docs/research/):

- **Identifiers saturate, quasi-identifiers accumulate.** A username is a
  primary key; adding bits to it is meaningless. Only QIs feed `combine()`.
- **Entropy is capped by sample size.** Any figure near log2(sample_n) is
  resolution-limited and flagged.
- **Uniqueness is not identification.** The reported number is the first link
  in a four-step chain, and the wording says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog, entropy, warehouse
from .config import WORLD_POPULATION


@dataclass
class Identifiability:
    """How identifiable the collected evidence makes the subject.

    Always a **lower bound on a bound**. `unmeasured` counts attributes with no
    entropy figure — they contribute nothing even though they plainly leak
    something. And the total itself is a composition bound, not an estimate:
    real attributes correlate, which is what `redundancy` corrects for.
    """

    bits: float
    anonymity_set: float
    budget: float
    redundancy: float
    redundancy_source: str
    population: int
    # Identifiers found in the evidence. Any one of these ends the question
    # independently of how many bits the quasi-identifiers add up to.
    identifiers: list[str] = field(default_factory=list)
    measured: list[tuple[str, float, int]] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    resolution_limited: list[str] = field(default_factory=list)

    @property
    def saturated(self) -> bool:
        """Whether a unique-by-construction identifier is present."""
        return bool(self.identifiers)

    @property
    def unique(self) -> bool:
        return self.saturated or entropy.is_unique(self.bits, self.population)

    def summary(self) -> str:
        if self.saturated:
            names = ", ".join(self.identifiers)
            return (
                f"Identified by construction: {names}. "
                f"Quasi-identifiers add {self.bits:.2f} bits on top, which is "
                f"redundant once a primary key is public."
            )
        line = entropy.describe(self.bits, self.population)
        if self.unmeasured:
            line += f" — floor only, {len(self.unmeasured)} attribute(s) unmeasured"
        return line


def _resolve_redundancy(attributes: list[str]) -> tuple[float, str]:
    """Pick a correlation discount, preferring a measured one over a guess.

    The 0.80 figure was measured on browser-fingerprint attributes observed
    together; applying it to attributes from a different surface would be
    borrowing a constant that was never measured there.
    """
    namespaces = {a.split("/", 1)[0] for a in attributes}
    if len(namespaces) == 1:
        only = next(iter(namespaces))
        if only in entropy.NAMESPACE_REDUNDANCY:
            return entropy.NAMESPACE_REDUNDANCY[only], f"measured for '{only}/' attributes"
    return 0.0, "assumed independent (upper bound — no measured value for this mix)"


def identifiability(
    redundancy: float | None = None, population: int = WORLD_POPULATION
) -> Identifiability:
    """Score every distinct attribute collected so far, in bits."""
    frame = warehouse.query("SELECT DISTINCT attribute FROM signals ORDER BY attribute")
    attributes = list(frame["attribute"]) if not frame.empty else []

    identifiers: list[str] = []
    measured: list[tuple[str, float, int]] = []
    unmeasured: list[str] = []
    limited: list[str] = []

    for attribute in attributes:
        entry = catalog.get(attribute)
        if entry is None:
            unmeasured.append(attribute)
            continue
        if entry.kind == "identifier":
            identifiers.append(attribute)
            continue
        if entry.kind == "attribute":
            continue  # payload, not a key — never accumulated
        if entry.entropy_bits is None or not entry.sample_n:
            unmeasured.append(attribute)
            continue
        measured.append((attribute, entry.entropy_bits, entry.sample_n))
        if entropy.resolution_limited(entry.entropy_bits, entry.sample_n):
            limited.append(attribute)

    resolved, source = (
        (redundancy, "caller-supplied")
        if redundancy is not None
        else _resolve_redundancy([a for a, _, _ in measured])
    )
    total = entropy.combine([b for _, b, _ in measured], redundancy=resolved)

    return Identifiability(
        bits=total,
        anonymity_set=entropy.anonymity_set(total, population),
        budget=entropy.population_bits(population),
        redundancy=resolved,
        redundancy_source=source,
        population=population,
        identifiers=sorted(identifiers),
        measured=sorted(measured, key=lambda row: row[1], reverse=True),
        unmeasured=unmeasured,
        resolution_limited=limited,
    )


def coverage() -> "list[dict]":
    """What has been collected, by source."""
    frame = warehouse.query(
        """
        SELECT source,
               COUNT(*)                    AS signals,
               COUNT(DISTINCT attribute)   AS attributes,
               MAX(observed_at)            AS last_observed
        FROM signals GROUP BY source ORDER BY signals DESC
        """
    )
    return frame.to_dict("records")


def inference_gap() -> "list[dict]":
    """Claims derived about the subject, undisclosed ones first.

    `verdict` and `effect` are independent: a claim can be wrong and still have
    changed a price, an ad, or an offer. Undisclosed-and-correct is the finding
    this lab exists to count; incorrect-and-operative is the one the industry
    would rather not discuss.
    """
    frame = warehouse.query(
        """
        SELECT claim, inferred_by, from_sources, disclosed, verdict, effect,
               confidence, method
        FROM inferences ORDER BY disclosed ASC, confidence DESC
        """
    )
    return frame.to_dict("records")
