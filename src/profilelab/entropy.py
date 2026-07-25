"""Identifiability arithmetic — how many people are left?

Every measurement in this lab reduces to that question. For an attribute value
observed with population frequency `p`, the self-information it carries is

    I = -log2(p)   bits

Independent attributes add, so a browser reporting a 1-in-1000 font list
(9.97 bits) and a 1-in-40 timezone (5.32 bits) has given up 15.29 bits, cutting
a population of 8.2 billion down to an anonymity set of ~200,000. The world
population is worth log2(8.2e9) = 32.93 bits: accumulate that much and the
anonymity set is one, which is to say, you.

**Independence is a lie.** Screen size correlates with operating system, city
with language, GitHub activity hours with timezone. Naively summing bits from
correlated attributes overstates identifiability — sometimes badly. `combine`
therefore takes an explicit `redundancy` discount, and the honest default when
correlation is unmeasured is to under-claim rather than over-claim. A profile
that says "you are anonymous" and is wrong is a much worse error here than one
that says "you are identifiable" and is pessimistic.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from .config import WORLD_POPULATION

# Measured on co-observed browser-fingerprint attributes: Berke et al. 2025
# report 13 attributes whose individual entropies sum to 33.454 bits but whose
# joint entropy is 12.101. Solving combine(bits, r) = 12.101 gives r ~= 0.80.
# Applies to fingerprint attributes measured together; do NOT assume it
# transfers to attributes from other surfaces.
# See docs/research/01-population-baseline.md.
MEASURED_REDUNDANCY = 0.80

# Per-namespace redundancy defaults. Absence means "unmeasured", which resolves
# to 0.0 — the independent sum, an upper bound on identifiability.
NAMESPACE_REDUNDANCY: dict[str, float] = {"fp": MEASURED_REDUNDANCY}


def sample_ceiling(n: int) -> float:
    """Maximum entropy measurable from a sample of `n` observations.

    You cannot observe more than log2(n) bits of distinction among n things.
    Every published fingerprint entropy is bounded this way: Berke's 8,400
    caps at 13.04 bits, Eckersley's 470k at 18.8, Gomez-Boix's 2M at ~21. A
    measurement at its ceiling means the instrument ran out of resolution, not
    that the true entropy was found.
    """
    if n < 1:
        raise ValueError(f"sample size must be >= 1, got {n!r}")
    return math.log2(n)


def resolution_limited(bits: float, sample_n: int, tolerance: float = 1.0) -> bool:
    """Whether a measurement is close enough to its sample ceiling to be suspect."""
    return bits >= sample_ceiling(sample_n) - tolerance


def surprisal(p: float) -> float:
    """Bits revealed by observing a value that occurs with probability `p`.

    p=1 (everyone shares it) reveals nothing; p=0.5 reveals exactly 1 bit.
    """
    if not 0.0 < p <= 1.0:
        raise ValueError(f"probability must be in (0, 1], got {p!r}")
    return -math.log2(p)


def bits_from_counts(matching: int, total: int) -> float:
    """Bits revealed by a value held by `matching` of `total` observed people."""
    if total <= 0:
        raise ValueError(f"total must be positive, got {total!r}")
    if not 0 < matching <= total:
        raise ValueError(f"matching must be in (0, {total}], got {matching!r}")
    return surprisal(matching / total)


def population_bits(population: int = WORLD_POPULATION) -> float:
    """The identification budget: bits needed to single out one of `population`."""
    if population < 1:
        raise ValueError(f"population must be >= 1, got {population!r}")
    return math.log2(population)


def anonymity_set(bits: float, population: int = WORLD_POPULATION) -> float:
    """How many people still match after `bits` have been revealed.

    Returned as a float and deliberately allowed below 1.0: a value of 0.02
    means the evidence over-determines a single person by ~5.6 bits, which is a
    meaningful thing to see rather than something to clamp away.
    """
    if bits < 0:
        raise ValueError(f"bits must be non-negative, got {bits!r}")
    return population / (2.0**bits)


def combine(bits: Iterable[float], redundancy: float = 0.0) -> float:
    """Total bits from several attributes, discounted for correlation.

    `redundancy` is the fraction of the naive sum assumed to be shared
    information: 0.0 treats the attributes as independent (an upper bound on
    identifiability), 1.0 treats them as perfectly correlated (worth nothing
    beyond the largest single attribute — the true floor).
    """
    if not 0.0 <= redundancy <= 1.0:
        raise ValueError(f"redundancy must be in [0, 1], got {redundancy!r}")
    values = [b for b in bits]
    if not values:
        return 0.0
    if any(b < 0 for b in values):
        raise ValueError("bits must be non-negative")
    total = math.fsum(values)
    floor = max(values)
    # Interpolate between the independent sum and the fully-correlated floor,
    # so the discount can never claim less information than the single
    # strongest attribute already proved.
    return total - redundancy * (total - floor)


# `population / 2**log2(population)` is not exactly 1.0 in binary floating
# point — for 8.2e9 it comes out at 1.0000000000000002. Without a tolerance the
# exactly-at-budget case, which is the definition of unique, would report False.
_UNIQUE_TOLERANCE = 1e-9


def is_unique(bits: float, population: int = WORLD_POPULATION) -> bool:
    """Whether `bits` is enough to identify one person out of `population`."""
    return anonymity_set(bits, population) <= 1.0 + _UNIQUE_TOLERANCE


def describe(bits: float, population: int = WORLD_POPULATION) -> str:
    """One-line human summary — used by `wmp entropy` and the MCP tools.

    Deliberately says "sample-unique", not "identified". Three separate results
    stand between the two, and this lab measures only the first:

        sample-unique -> population-unique -> linkable -> identified

    Sample uniqueness does not imply population uniqueness, and population
    uniqueness does not imply reidentification — an adversary still needs an
    identified source to link against. See docs/research/04-behavioral-traces.md
    and docs/research/05-linkage.md.
    """
    remaining = anonymity_set(bits, population)
    budget = population_bits(population)
    if is_unique(bits, population):
        over = bits - budget
        return (
            f"{bits:.2f} bits — enough to be unique in a population of "
            f"{population:,}, with {over:.2f} to spare (uniqueness, not identification)"
        )
    return f"{bits:.2f} of {budget:.2f} bits — {remaining:,.0f} people still match"
