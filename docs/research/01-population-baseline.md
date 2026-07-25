# Dig 1 — the population baseline

**Question.** How do you estimate `p(v)` for an attribute without owning a
population sample? This is the blocker that makes `wmp entropy` return 0.00.

## What the measurements actually say

Four studies, same technique, wildly different answers:

| Study | Sample | Recruitment | % unique |
|---|---|---|---|
| Eckersley 2010 (Panopticlick) | 470,161 | self-selected, privacy-interested | 83.6–94.2% |
| Laperdrix 2016 (AmIUnique) | 118,934 | self-selected, tech media | 89.4% desktop / 81% mobile |
| Gómez-Boix 2018 (WWW) | >2,000,000 | **real traffic**, French news site | **33.6%** |
| Berke 2025 (PoPETs) | 8,400 | paid panel, US-representative | 60.2% |

The spread is not measurement noise, it is **sampling**. Panopticlick and
AmIUnique recruited through Slashdot, Ars Technica and social media; their
respondents are unusual browsers by construction. When Gómez-Boix ran the same
17 attributes against ordinary traffic, uniqueness fell by two thirds.

Berke et al. also found that **women were significantly less likely to consent
to sharing browser data**, so the historical datasets carry a gender skew whose
effect on published entropy was never controlled for.

## The finding that changes our code

Berke et al. (Dec 2023, 13 attributes, US panel) publish per-attribute Shannon
entropy *and* the joint entropy of the combined fingerprint:

| Attribute | Distinct | % unique | Entropy (bits) |
|---|---|---|---|
| WebGL unmasked renderer | 654 | 3.2 | 6.833 |
| Screen resolution | 572 | 4.5 | 5.510 |
| User agent | 434 | 2.8 | 4.613 |
| WebGL unmasked vendor | 36 | 0.1 | 3.313 |
| Hardware concurrency | 24 | 0.1 | 2.340 |
| Platform | 12 | 0 | 2.114 |
| Timezone | 49 | 0.2 | 2.064 |
| Languages | 264 | 1.7 | 1.730 |
| Device memory | 7 | 0 | 1.611 |
| Touch points | 11 | 0 | 1.463 |
| WebGL renderer | 36 | 0.1 | 0.782 |
| Color depth | 3 | 0 | 0.616 |
| WebGL vendor | 3 | 0 | 0.465 |
| **Combined fingerprint** | 5,973 | **60.2** | **12.101** |

**The naive sum of those 13 attributes is 33.45 bits. The measured joint
entropy is 12.101.** Summing independent bits overstates identifiability by
21.35 bits here — a factor of 2.6 million in anonymity-set terms.

This is the single best empirical validation of the redundancy discount, and it
yields a measured default. Solving

```
combine(bits, r) = Σb − r·(Σb − max b)
12.101 = 33.454 − r·(33.454 − 6.833)
```

gives **r ≈ 0.80** for browser-fingerprint attributes. That is now the
documented default in `entropy.py`, replacing an arbitrary 0.0.

Note also that 33.45 bits ≈ the 32.93-bit world-population budget. Taken
naively, the sum would have claimed every browser on earth is uniquely
identifiable among all humanity. The measured value says the anonymity set is
about 2¹²·¹ ≈ 4,400 — *within that sample*.

## The methodological trap: entropy is capped by sample size

You cannot measure more than `log₂(N)` bits from a sample of N. Berke's 8,400
participants cap at 13.04 bits; the measured 12.101 sits just under that
ceiling, which means **the true entropy is unknown and larger** — the
instrument ran out of resolution, it did not find the answer.

The same applies to every figure above: Eckersley's 470k caps at 18.8 bits,
Gómez-Boix's 2M at ~21 bits. All published fingerprint entropies are
sample-limited lower bounds. Any of them quoted against the 32.93-bit world
budget is a category error.

Berke et al. state the related trap directly: these metrics are **not scale
invariant**. Average anonymity-set size grows roughly linearly with sample
size, while % unique falls toward a limit. Comparing two groups of different
sizes is therefore meaningless without correction — they resample to equal
group sizes (n=1,800; 1,000 repetitions; 95% CIs) before comparing. Their
Hispanic example makes the point: 63% vs 60% unique unsampled, identical after
equal-size resampling.

## Decisions taken

1. **Adopt Berke 2023 as the primary reference prior**, replacing Eckersley
   2010 as the default. Eckersley is retained but marked historical: its
   richest surface, the NPAPI plugin list at 15.4 bits, no longer exists.
2. **Record `sample_n` with every entropy figure**, and expose
   `entropy.sample_ceiling(n) = log₂(n)`. Any claimed total at or above the
   ceiling of its source sample is flagged as resolution-limited.
3. **Stop reporting bits against world population by default.** The honest
   denominator is the population the measurement came from.
4. **Default redundancy 0.80** for co-measured fingerprint attributes, with
   provenance, rather than a bare 0.0.

## Still open

- No equivalent measured baseline exists for the broadcast half (GitHub,
  writing). Those attributes stay unmeasured rather than guessed.
- Sub-population denominators: the anonymity set that matters is usually a
  subgroup (your city, your employer), not humanity. See [Dig 2](02-adversary-model.md).

## Sources

- [Eckersley 2010, *How Unique Is Your Web Browser?*](https://coveryourtracks.eff.org/)
- [Laperdrix et al. 2016, AmIUnique](https://amiunique.org)
- [Gómez-Boix, Laperdrix, Baudry 2018, *Hiding in the Crowd* (WWW)](https://inria.hal.science/hal-01718234v2)
- [Berke et al. 2025, *How Unique is Whose Web Browser?* (PoPETs 2025(1):720–758)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf)
