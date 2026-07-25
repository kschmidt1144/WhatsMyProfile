# Dig 2 — the adversary model

**Question.** "You have leaked 12 bits" — to *whom*? The lab computes exposure
against an abstract observer, which is not a thing that exists.

## LINDDUN

The established privacy-threat taxonomy is LINDDUN (KU Leuven), incorporated
into ISO 27550 and cited in the EDPS opinion on privacy by design. Seven
categories:

| | Threat | Our coverage |
|---|---|---|
| **L** | **Linkability** — joining two items of interest *without* knowing whose they are | `identities` table, unexercised — see [Dig 5](05-linkage.md) |
| **I** | **Identifiability** — pinning a record to a person | `entropy.py` — the only one we actually model |
| **N** | Non-repudiation — the subject cannot deny an action | not modelled |
| **D** | Detectability — knowing an item *exists* without reading it | not modelled |
| **D** | Disclosure of information — reading the data itself | `signals` |
| **U** | **Unawareness** — the subject does not know what is held or derived | this is precisely the inference gap |
| **N** | Non-compliance — processing violates policy or law | the SAR half, [Dig 7](07-consequence.md) |

Two things fall out immediately.

**Linkability and identifiability are separate threats.** LINDDUN keeps them
apart because they have different mitigations and different thresholds — an
adversary can link all your sessions into one coherent profile while never
learning your name, and that profile is still a dossier. Our schema collapses
both into "bits", which cannot express the distinction.

**Unawareness is a named threat, and it is the one this project measures.** The
inference gap is not a novel metric invented here; it is LINDDUN's U category
with a number attached. Useful framing to adopt rather than reinvent.

The standard formalisation of the observer is **honest-but-curious**: a
legitimate participant that performs its function faithfully while learning
whatever it can from what passes through. That is the right default adversary
for a platform, and the wrong one for a broker or a stalker.

## Why one number cannot be right

Exposure is relative to what an adversary can see, and the visible sets barely
overlap:

| Adversary | Sees | Cannot see | Typical goal |
|---|---|---|---|
| **Platform** (honest-but-curious) | everything you do on it, logged-in and deterministic | other platforms | retention, ad targeting |
| **Ad-tech / broker** | fragments across many sites, probabilistically joined | your login identity, mostly | segment resale |
| **Stranger with a search box** | the broadcast half only | ambient signals entirely | one-off identification |
| **Employer / insurer** | broadcast half plus records you gave them | ambient | decisions about you |
| **State actor** | can compel any of the above | little | targeted |

The same 12 bits mean different things in each row. Worse, the *denominator*
changes with the adversary: a stranger identifying you among 8.2 billion needs
32.93 bits, but an employer picking you out of 400 employees needs 8.6. **The
harder the adversary's prior narrowing, the fewer bits they need** — which is
why sub-population denominators matter more than the world figure.

## Berke's demographic result belongs here

Risk is not uniform across people either. In the Berke 2025 US panel:

- Fingerprinting risk **decreases monotonically with income** — lowest-income
  users are the most identifiable.
- % unique **increases with age** — oldest users are most at risk, and were
  also the most concerned.
- Men had more unique overall fingerprints; women had more unique **User agent**
  values, putting them at greater risk of *passive* fingerprinting (HTTP
  headers, undetectable by the browser).
- The `Languages` attribute carries higher risk for Hispanic and non-White
  users — `es-US` speakers are 11% of the sample but >45% of one attribute
  value.

"Privacy for whom?" is a real question with a measurable answer, and a lab that
reports one global number cannot ask it.

## Decision taken

Add an **adversary dimension** before the schema calcifies. Concretely:

- `adversaries` — id, class, `population` (their prior narrowing, i.e. the
  denominator to score against), `linkage` (deterministic | probabilistic | none).
- `signals.visible_to` — which adversary classes observe this signal.
- `wmp entropy --adversary broker` scores only the visible subset against that
  adversary's population.

This is deferred to implementation rather than done in this pass, but it is now
a schema requirement rather than a nice-to-have, and the roadmap reflects it.

## Still open

- Modelling the state actor honestly probably means "assume compelled access to
  every other row", which makes its number trivial and uninteresting. Possibly
  it should be excluded rather than badly modelled.
- Adversaries collude. Broker data flows to platforms and back. A per-adversary
  score understates a coalition, and the coalition lattice is large.

## Sources

- [LINDDUN privacy threat modeling](https://linddun.org/) — overview via
  [Warner, *LINDDUN Privacy Threat Modeling*](https://warnerchad.medium.com/linddun-privacy-threat-modeling-ae47438abf24)
  and [Security Compass, STRIDE vs LINDDUN vs PASTA](https://www.securitycompass.com/blog/comparing-stride-linddun-pasta-threat-modeling/)
- [Berke et al. 2025 (PoPETs)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §6.2, §8.2
