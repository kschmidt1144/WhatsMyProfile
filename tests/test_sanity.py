"""Sanity suite — offline by design; no test touches the network.

Two things are pinned here. The identifiability arithmetic, because every
figure the project will ever publish is downstream of it, and the .gitignore,
because this repo is public and the cost of that particular mistake is not
recoverable by a follow-up commit.
"""

from __future__ import annotations

import inspect
import json
import math
import subprocess
from pathlib import Path

import pytest

from profilelab import analysis, catalog, entropy, reading, sources, truth
from profilelab.config import ROOT, WORLD_POPULATION
from profilelab.model import Attribute, Inference, Signal
from profilelab.sources import adprefs, github
from profilelab.sources.adprefs import base as adprefs_base
from profilelab.sources.adprefs import linkedin as linkedin_ads
from profilelab.sources.adprefs import x as x_ads

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
    assert catalog.known_bits("fp/user_agent") == pytest.approx(4.613)


def test_model_rejects_invalid_metadata():
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="nonsense")
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="device", sensitivity="very-secret")
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="device", kind="primary-key")
    with pytest.raises(ValueError):
        Signal("me", "id", "src", "x/y", "v", "now", "ev", confidence=1.5)
    with pytest.raises(ValueError):
        Inference("me", "claim", "by", "src", disclosed=False, verdict="maybe")
    with pytest.raises(ValueError):
        Inference("me", "claim", "by", "src", disclosed=False, effect="massive")


def test_entropy_figure_requires_its_sample_size():
    """A bits figure without sample_n cannot be read as a floor, so reject it."""
    with pytest.raises(ValueError):
        Attribute("x/y", "X", category="device", entropy_bits=4.0)
    Attribute("x/y", "X", category="device", entropy_bits=4.0, sample_n=1000)  # fine


def test_identifiers_are_marked_as_such():
    """A username is a primary key, not a trait shared with a fraction of people."""
    assert catalog.kind_of("github/login") == "identifier"
    assert catalog.kind_of("github/email") == "identifier"
    assert catalog.kind_of("fp/user_agent") == "quasi_identifier"
    assert catalog.kind_of("inferred/timezone") == "attribute"


# ── sample-size limits on entropy ────────────────────────────────────────────


def test_sample_ceiling_is_log2_of_n():
    assert entropy.sample_ceiling(1024) == pytest.approx(10.0)
    assert entropy.sample_ceiling(8400) == pytest.approx(13.04, abs=0.01)
    assert entropy.sample_ceiling(470_161) == pytest.approx(18.84, abs=0.01)


def test_resolution_limited_flags_measurements_at_their_ceiling():
    # 12.101 bits measured on n=8,400 (ceiling 13.04) is instrument-limited.
    assert entropy.resolution_limited(12.101, 8400)
    # 4.613 bits on the same sample has plenty of headroom.
    assert not entropy.resolution_limited(4.613, 8400)


def test_measured_redundancy_reproduces_the_joint_fingerprint_entropy():
    """Pin the 0.80 default to the measurement it was derived from.

    Berke et al. report 13 co-measured browser attributes plus the joint
    entropy of the combined fingerprint. If combine() with MEASURED_REDUNDANCY
    stops landing on their joint figure, the constant has drifted from its
    source and the docs are lying.
    """
    berke = [a for a in catalog.ATTRIBUTES if a.sample_n == 8400 and a.entropy_bits is not None]
    assert len(berke) == 13, "expected the 13 co-measured Berke attributes"

    bits = [a.entropy_bits for a in berke]
    assert sum(bits) == pytest.approx(33.45, abs=0.01)  # the naive, wrong answer
    assert max(bits) == pytest.approx(6.833)

    combined = entropy.combine(bits, redundancy=entropy.MEASURED_REDUNDANCY)
    assert combined == pytest.approx(12.101, abs=0.1)  # the measured joint entropy


def test_naive_summing_would_have_claimed_global_uniqueness():
    """Why the redundancy discount is not optional.

    Summed independently the fingerprint attributes come to ~33.45 bits, just
    over the 32.93-bit world budget — i.e. the naive arithmetic claims every
    browser on earth is uniquely identifiable among all humanity. The measured
    joint entropy leaves an anonymity set in the thousands.
    """
    berke = [a.entropy_bits for a in catalog.ATTRIBUTES if a.sample_n == 8400 and a.entropy_bits]
    assert entropy.is_unique(sum(berke), WORLD_POPULATION)  # the false claim
    honest = entropy.combine(berke, redundancy=entropy.MEASURED_REDUNDANCY)
    assert not entropy.is_unique(honest, WORLD_POPULATION)
    assert entropy.anonymity_set(honest, WORLD_POPULATION) > 1_000_000


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


# ── ad-preference connectors ─────────────────────────────────────────────────


def test_x_parser_reads_inferred_demographics_and_skips_disabled_interests(tmp_path):
    payload = {
        "p13nData": {
            "demographics": {
                "genderInfo": {"gender": "male"},
                "age": {"ageRange": "35-49"},
                "languages": [{"language": "English"}],
            },
            "interests": {
                "interests": [
                    {"name": "Technology", "isDisabled": False},
                    {"name": "Angling", "isDisabled": True},
                ],
                "audienceAndAdvertisers": {"advertisers": ["@someretailer"]},
            },
        }
    }
    path = tmp_path / "personalization.js"
    path.write_text("window.YTD.personalization.part0 = " + json.dumps([payload]))

    claims = x_ads._parse(path)
    topics = {c.topic for c in claims}
    assert "Technology" in topics
    assert "gender = male" in topics
    assert "age range = 35-49" in topics
    # An interest the user switched off is not part of the live profile.
    assert "Angling" not in topics
    assert any(c.facet == "advertiser" and c.topic == "@someretailer" for c in claims)


def test_linkedin_separates_what_you_typed_from_what_was_inferred(tmp_path):
    path = tmp_path / "Ad_Targeting.csv"
    path.write_text("Job Titles,Interests,Member Age\nEngineer;Architect,Cycling,25-34\n")

    claims = {c.topic: c for c in linkedin_ads._parse(path)}
    # A job title is something the member entered.
    assert claims["Engineer"].disclosed is True
    assert claims["Architect"].disclosed is True
    # An interest is something LinkedIn decided.
    assert claims["Cycling"].disclosed is False
    # Demographics keep their key — "25-34" alone means nothing.
    assert claims["member age = 25-34"].facet == "demographic"


def test_interest_topics_are_emitted_bare_so_platforms_can_be_compared(tmp_path):
    """Cross-platform agreement is the whole point; prefixed topics never match.

    X emits "Technology"; if LinkedIn emitted "Interests: Technology" the two
    would never group together and every comparison would read as divergence.
    """
    li = tmp_path / "Ad_Targeting.csv"
    li.write_text("Interests\nTechnology\n")
    xa = tmp_path / "personalization.js"
    xa.write_text(
        "window.YTD.personalization.part0 = "
        + json.dumps([{"p13nData": {"interests": {"interests": [{"name": "Technology"}]}}}])
    )

    li_topics = {c.topic for c in linkedin_ads._parse(li) if c.facet == "interest"}
    x_topics = {c.topic for c in x_ads._parse(xa) if c.facet == "interest"}
    assert li_topics & x_topics == {"Technology"}


def test_linkedin_inferences_keeps_only_affirmative_rows(tmp_path):
    path = tmp_path / "Inferences.csv"
    path.write_text(
        "Category,Type of inference,Description,Inference\n"
        "Interest,Interested in cycling,derived,Yes\n"
        "Interest,Owns a car,derived,No\n"
    )
    topics = {c.topic for c in linkedin_ads._parse(path)}
    assert "Interested in cycling" in topics
    assert "Owns a car" not in topics


def test_advertiser_lists_are_signals_but_not_inferences():
    """Who holds your data is a fact about them, not a claim about you."""
    _, advertiser_is_inference = adprefs_base.FACETS["advertiser"]
    assert advertiser_is_inference is False
    assert adprefs_base.FACETS["interest"][1] is True
    assert adprefs_base.FACETS["demographic"][1] is True


def test_tolerant_json_walker_survives_a_restructured_export(tmp_path):
    """Meta and Google rename things; over-collect rather than report empty."""
    path = tmp_path / "ad_preferences.json"
    path.write_text(json.dumps({"topics": {"v2": [{"name": "Cycling"}, {"name": "Coffee"}]}}))
    topics = {c.topic for c in adprefs_base.json_topics(path)}
    assert topics == {"Cycling", "Coffee"}


def test_missing_export_is_unavailable_not_an_error():
    """An absent archive must read as 'not configured', never as an empty profile."""
    for module in adprefs.PLATFORMS:
        assert isinstance(module.available(), bool)


# ── ground truth ─────────────────────────────────────────────────────────────


@pytest.fixture
def truth_store(tmp_path, monkeypatch):
    monkeypatch.setattr(truth, "STORE", tmp_path / "verdicts.json")
    return tmp_path / "verdicts.json"


def test_claim_key_is_stable_across_whitespace_and_case(truth_store):
    a = truth.claim_key("google_ads", "interest: Relocation & Household Moving")
    b = truth.claim_key("GOOGLE_ADS", "interest:  relocation & household   moving")
    assert a == b


def test_verdict_round_trips(truth_store):
    truth.record("google_ads", "interest: Baseball", "correct")
    assert truth.verdict_for("google_ads", "interest: Baseball") == "correct"
    assert truth.verdict_for("google_ads", "interest: Jewelry") is None


def test_verdict_must_be_a_known_value(truth_store):
    with pytest.raises(ValueError):
        truth.record("google_ads", "interest: Baseball", "probably")


def test_rescoring_overwrites_rather_than_duplicates(truth_store):
    truth.record("google_ads", "interest: Baseball", "correct")
    truth.record("google_ads", "interest: Baseball", "incorrect")
    assert truth.verdict_for("google_ads", "interest: Baseball") == "incorrect"
    assert len(truth.load()) == 1


def test_orphaned_verdicts_are_surfaced_not_silently_carried(truth_store):
    """A platform rewording a topic must not leave a verdict attached to nothing."""
    truth.record("google_ads", "interest: Fishing", "correct")
    still_present = {truth.claim_key("google_ads", "interest: Baseball")}
    orphaned = truth.orphans(still_present)
    assert len(orphaned) == 1
    assert orphaned[0]["claim"] == "interest: Fishing"


def test_forget_and_clear(truth_store):
    truth.record("google_ads", "interest: Baseball", "correct")
    truth.record("google_ads", "interest: Food", "correct")
    assert truth.forget("google_ads", "interest: Baseball") is True
    assert truth.forget("google_ads", "interest: Baseball") is False
    assert truth.clear() == 1
    assert truth.load() == {}


def test_accuracy_excludes_unverifiable_and_is_none_when_undecided():
    """An unadjudicable claim says nothing about the inferrer, so it must not
    count as a failure — and no decisions must yield None, not a bogus 0%."""
    undecided = analysis.Scorecard(total=5, scored=2, correct=0, incorrect=0, unverifiable=2,
                                   undisclosed_correct=0)
    assert undecided.accuracy is None
    assert undecided.unscored == 3

    mixed = analysis.Scorecard(total=10, scored=10, correct=6, incorrect=2, unverifiable=2,
                               undisclosed_correct=5)
    assert mixed.accuracy == pytest.approx(0.75)  # 6/8, not 6/10


def test_wilson_interval_is_wide_at_small_n():
    """The guard against reading a point estimate as a result.

    16/19 looks like it beats an 80% benchmark. The interval says a sample this
    size cannot tell the two apart, and the scorecard must not claim otherwise.
    """
    lo, hi = analysis.wilson_interval(16, 19)
    assert lo < analysis.INDUSTRY_INTEREST_ACCURACY < hi
    assert hi - lo > 0.25  # spans more than 25 points

    # A large sample at the same rate does separate them.
    lo_big, hi_big = analysis.wilson_interval(1600, 1900)
    assert lo_big > analysis.INDUSTRY_INTEREST_ACCURACY
    assert hi_big - lo_big < 0.05


def test_wilson_interval_stays_in_bounds_at_extremes():
    assert analysis.wilson_interval(0, 5)[0] == 0.0
    assert analysis.wilson_interval(5, 5)[1] == 1.0
    with pytest.raises(ValueError):
        analysis.wilson_interval(0, 0)


# ── LLM readings ─────────────────────────────────────────────────────────────


def test_briefing_never_reads_the_answer_key():
    """The briefing must not carry verdicts or prior inferences.

    Verdicts are ground truth — a briefing containing them would measure
    reading comprehension, not inference. Prior inferences turn "what can you
    derive?" into "do you agree with Google?", a different and easier question.
    Asserted against the query itself, so a later edit that joins `inferences`
    fails here rather than silently invalidating every reading.
    """
    source = inspect.getsource(reading.briefing)
    query = source[source.index("SELECT") : source.index("ORDER BY")].lower()
    assert "from signals" in query
    for forbidden in ("inference", "verdict", "scored", "disclosed"):
        assert forbidden not in query, f"briefing query must not touch {forbidden!r}"


def test_reading_source_name_matches_between_storage_and_claims():
    """Verdicts key on from_sources; a mismatch would orphan every score."""
    store_src = inspect.getsource(reading.store)
    read_src = inspect.getsource(reading.read)
    assert "write_tidy(SOURCE" in store_src
    assert "from_sources=SOURCE" in read_src


def test_reading_uses_the_current_default_model():
    assert reading.DEFAULT_MODEL == "claude-opus-5"


def test_reading_claim_schema_round_trips():
    parsed = reading.Reading.model_validate(
        {"claims": [{"claim": "lives in US Eastern time", "category": "location",
                     "confidence": 0.7, "basis": "push-hour histogram"}]}
    )
    assert parsed.claims[0].category in reading.CATEGORIES
    assert 0.0 <= parsed.claims[0].confidence <= 1.0


def test_reading_prompt_asks_for_inference_not_restatement():
    """The failure mode in Finding 2 was narrative built on restated signals."""
    assert "not an inference" in reading.PROMPT
    assert "{briefing}" in reading.PROMPT


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
        # Browser-automation output captured while driving a logged-in session.
        ".playwright-mcp/page-2026.yml",
        "amazon-signin.png",
        # Ground truth — higher-order personal data than anything else here.
        "data/truth/verdicts.json",
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
