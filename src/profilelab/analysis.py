"""Turning collected signals into the one number the project is about."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog, entropy, warehouse
from .config import WORLD_POPULATION


@dataclass
class Identifiability:
    """How identifiable the collected evidence makes the subject.

    Always a **lower bound**. `unmeasured` counts attributes present in the
    warehouse that have no entropy figure yet; they contribute nothing to
    `bits` even though they plainly leak something in reality. Reading this
    number as "how exposed I am" is wrong — it is "how exposed I can already
    prove I am".
    """

    bits: float
    anonymity_set: float
    budget: float
    redundancy: float
    measured: list[tuple[str, float]] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)

    @property
    def unique(self) -> bool:
        return entropy.is_unique(self.bits)

    def summary(self) -> str:
        line = entropy.describe(self.bits, WORLD_POPULATION)
        if self.unmeasured:
            line += f" (lower bound: {len(self.unmeasured)} attribute(s) not yet measured)"
        return line


def identifiability(redundancy: float = 0.0, population: int = WORLD_POPULATION) -> Identifiability:
    """Score every distinct attribute collected so far, in bits."""
    frame = warehouse.query("SELECT DISTINCT attribute FROM signals ORDER BY attribute")
    attributes = list(frame["attribute"]) if not frame.empty else []

    measured: list[tuple[str, float]] = []
    unmeasured: list[str] = []
    for attribute in attributes:
        bits = catalog.known_bits(attribute)
        if bits is None:
            unmeasured.append(attribute)
        else:
            measured.append((attribute, bits))

    total = entropy.combine([b for _, b in measured], redundancy=redundancy)
    return Identifiability(
        bits=total,
        anonymity_set=entropy.anonymity_set(total, population),
        budget=entropy.population_bits(population),
        redundancy=redundancy,
        measured=sorted(measured, key=lambda pair: pair[1], reverse=True),
        unmeasured=unmeasured,
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

    The undisclosed-and-correct rows are the finding this lab exists to count.
    """
    frame = warehouse.query(
        """
        SELECT claim, inferred_by, from_sources, disclosed, verdict, confidence, method
        FROM inferences ORDER BY disclosed ASC, confidence DESC
        """
    )
    return frame.to_dict("records")
