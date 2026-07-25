"""Sanity suite — offline by design; no test touches the network.

Two things are pinned here. The identifiability arithmetic, because every
figure the project will ever publish is downstream of it, and the .gitignore,
because this repo is public and the cost of that particular mistake is not
recoverable by a follow-up commit.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import pytest

from profilelab import catalog, entropy, sources
from profilelab.config import ROOT, WORLD_POPULATION
from profilelab.model import Attribute, Inference, Signal
from profilelab.sources import github

# ── identifiability arithmetic ───────────────────────────────────────────────


def test_surprisal_endpoints():
    assert entropy.surprisal(1.0) == 0.0  # everyone shares it: reveals nothing
    assert entropy.surprisal(0.5) == pytest.approx(1.0)
    assert entropy.surprisal(0.25) == pytest.approx(2.0)


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5])
def test_surprisal_rejects_impossible_probabilities(bad):
    with pytest.raises(ValueError):
        entropy.surprisal(bad)


def test_world_population_costs_about_33_bits():
    """The number the whole project is calibrated against."""
    assert entropy.population_bits(WORLD_POPULATION) == pytest.approx(32.93, abs=0.01)


def test_full_budget_leaves_exactly_one_person():
    budget = entropy.population_bits(WORLD_POPULATION)
    assert entropy.anonymity_set(budget, WORLD_POPULATION) == pytest.approx(1.0)
    assert entropy.is_unique(budget, WORLD_POPULATION)
    assert not entropy.is_unique(budget - 1, WORLD_POPULATION)


def test_anonymity_set_halves_per_bit():
    assert entropy.anonymity_set(0, 1024) == 1024
    assert entropy.anonymity_set(1, 1024) == 512
    assert entropy.anonymity_set(10, 1024) == 1


def test_bits_from_counts_matches_surprisal():
    assert entropy.bits_from_counts(1, 1000) == pytest.approx(math.log2(1000))
    assert entropy.bits_from_counts(1000, 1000) == 0.0


def test_combine_independent_sums_and_correlated_floors():
    bits = [4.0, 3.0, 2.0]
    assert entropy.combine(bits, redundancy=0.0) == pytest.approx(9.0)
    # Fully correlated attributes are worth no more than the strongest one.
    assert entropy.combine(bits, redundancy=1.0) == pytest.approx(4.0)
    assert entropy.combine(bits, redundancy=0.5) == pytest.approx(6.5)
    assert entropy.combine([]) == 0.0


def test_combine_never_claims_less_than_its_strongest_attribute():
    """The discount interpolates toward the floor; it must not cross it."""
    for redundancy in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert entropy.combine([9.0, 1.0, 1.0], redundancy=redundancy) >= 9.0


def test_over_identification_is_visible_not_clamped():
    over = entropy.population_bits(WORLD_POPULATION) + 5
    assert entropy.anonymity_set(over, WORLD_POPULATION) < 1.0


# ── catalog integrity ────────────────────────────────────────────────────────


def test_attribute_ids_are_unique():
    ids = [a.attribute for a in catalog.ATTRIBUTES]
    assert len(ids) == len(set(ids))


def test_every_attribute_is_namespaced():
    assert all("/" in a.attribute for a in catalog.ATTRIBUTES)


def test_reference_entropies_are_carried_with_their_provenance():
    """A bits figure this lab did not measure must say where it came from."""
    for entry in catalog.ATTRIBUTES:
        if entry.entropy_bits is not None:
            assert entry.note, f"{entry.attribute} has entropy but no provenance note"


def test_unmeasured_attributes_read_as_none_not_zero():
    """Treating unmeasured as 0.0 would silently understate every total."""
    assert catalog.known_bits("fp/canvas_hash") is None
    assert catalog.known_bits("nonexistent/attribute") is None
    assert catalog.known_bits("fp/user_agent") == pytest.approx(10.0)


def test_model_rejects_invalid_metadata():
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="nonsense")
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="device", sensitivity="very-secret")
    with pytest.raises(ValueError):
        Signal("me", "id", "src", "x/y", "v", "now", "ev", confidence=1.5)
    with pytest.raises(ValueError):
        Inference("me", "claim", "by", "src", disclosed=False, verdict="maybe")


# ── connector contract ───────────────────────────────────────────────────────


def test_every_connector_satisfies_the_contract():
    assert sources.REGISTRY, "no connectors registered"
    for name, module in sources.REGISTRY.items():
        assert module.SOURCE == name
        assert module.TITLE
        assert module.MODE in {"broadcast", "ambient", "broker", "inference"}
        for hook in ("available", "fetch", "parse"):
            assert callable(getattr(module, hook)), f"{name} is missing {hook}()"


def test_unknown_source_is_a_clear_error():
    with pytest.raises(KeyError):
        sources.get("does-not-exist")


# ── the timezone inference (pure maths, no network) ──────────────────────────


def test_sleep_trough_recovers_a_utc_offset():
    """Someone at UTC-4 sleeping 23:00-07:00 local is quiet 03:00-11:00 UTC."""
    counts = [10] * 24
    for hour in range(3, 11):
        counts[hour] = 0
    offset, confidence = github.infer_utc_offset(counts)
    assert offset == -4
    assert confidence == pytest.approx(1.0)


def test_offset_recovery_round_trips_across_the_globe():
    for expected in range(-11, 12):
        counts = [10] * 24
        # Local 23:00-07:00 asleep -> UTC hours (23 - offset) ... (07 - offset).
        for i in range(8):
            counts[(23 - expected + i) % 24] = 0
        offset, _ = github.infer_utc_offset(counts)
        assert offset == expected, f"expected UTC{expected:+d}, got UTC{offset:+d}"


def test_flat_activity_yields_no_confidence():
    """A bot, or a scheduler, has no sleep window — say so instead of guessing."""
    _, confidence = github.infer_utc_offset([10] * 24)
    assert confidence == 0.0


def test_thin_evidence_is_discounted():
    counts = [0] * 24
    counts[12] = 3  # three events total: a shape, but not a meaningful one
    _, confidence = github.infer_utc_offset(counts)
    assert confidence < 0.1


def test_no_activity_returns_nothing():
    assert github.infer_utc_offset([0] * 24) is None


def test_histogram_must_have_24_bins():
    with pytest.raises(ValueError):
        github.infer_utc_offset([1] * 23)


# ── the guard that matters most ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "data/warehouse.duckdb",
        "data/raw/github/user.json",
        "data/tidy/github/signals.parquet",
        ".env",
        "exports/takeout.zip",
        "subject-access/acxiom-response.pdf",
        "capture.har",
        "report/figures/bits.png",
    ],
)
def test_personal_data_paths_are_gitignored(path):
    """This repo is public. A leak here is not fixable by a later commit."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(
        ["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True
    )
    assert result.returncode == 0, f"{path} is NOT gitignored"


def test_env_example_is_still_committable():
    """The template must survive the .env* ignore rule — it carries no secrets."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env.example"], cwd=ROOT, capture_output=True
    )
    assert result.returncode != 0, ".env.example must not be ignored"
