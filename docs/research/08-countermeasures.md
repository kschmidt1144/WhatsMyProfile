# Dig 8 — countermeasures that actually work

**Question.** Most privacy advice is folklore. Which interventions reduce bits,
and which raise them?

## The anonymity-set paradox

Identifiability is relative to a crowd. Any change that makes your configuration
*unusual* shrinks your crowd — including changes made in the name of privacy.
The literature is consistent on this:

- Privacy extensions **can increase uniqueness**. Extensions are themselves
  detectable, and the *set* of extensions you run is a fingerprint. "To Extend
  or not to Extend" showed browser extensions and web logins are independently
  fingerprintable surfaces.
- **Inconsistent or noisy spoofing makes you more unique**, not less. A browser
  reporting a User-Agent that contradicts its feature set is rarer than either
  honest configuration.
- Adding fonts, tweaking settings, running an unusual OS: each is an
  identifying choice.

"Blend in" beats "block everything". This is counterintuitive enough that most
advice gets it backwards.

## Uniformity versus randomization

Two coherent strategies exist; only one is deployed at scale.

**Uniformity** — make every user present the *same* fingerprint. Tor Browser's
approach: whether the user is on Windows, macOS or Linux, it reports Windows.
The goal is to minimise the number of distinguishable buckets per metric.
Independent tests put uniformity-first designs ahead of the alternatives.

The costs are real. The Tor fingerprint is itself well known — you are anonymous
*within* the Tor crowd and conspicuous outside it, which merely relocates the
question to whether "is a Tor user" is a bit you can afford. And the API
restrictions make it impractical for mainstream daily browsing, which is why
other vendors chose randomization or blocklists instead.

**Randomization** — return different values per session so no stable key forms.
Defeats naive linkage; detectable as randomization; and per [Dig 5](05-linkage.md)
the linkage attacks that matter are robust to perturbation, so noise buys less
than it appears to.

## Mitigations that create different harms

Berke et al. document a clean example. The `Device memory` API deliberately
rounds to the nearest power of 2 to *reduce* fingerprinting entropy. It works —
7 distinct values, 0% unique. But by bucketing users it becomes a demographic
grouping signal: users under $50k household income are 35% of the sample and
more than 60% of `deviceMemory = 2.0`.

**The mitigation reduced identification risk and increased inference risk.**
Exactly the decoupling from [Dig 3](03-k-anonymity-and-dp.md) and
[Dig 6](06-inference-gap.md), now with a browser API as the worked example. Any
countermeasure evaluated on identification alone can be net-harmful.

## The known negative result

Staab et al. tested the two obvious defences against LLM inference from text:
**industry-grade text anonymisation and model alignment are both currently
ineffective**. Stripping names and places does not stop a model inferring
location from dialect, idiom and incidental detail.

For the broadcast half of this lab, that means there is no known countermeasure
short of not publishing. Worth stating plainly rather than implying a fix exists.

## Decisions taken

1. **Measure interventions in bits, within-subject.** Baseline, apply one
   change, re-measure. Report the delta with its sample caveat
   ([Dig 1](01-population-baseline.md)).
2. **Score every countermeasure on both axes** — identification *and* inference.
   A single-axis evaluation would have scored the Device-memory API a success.
3. **Expect and publish negative results.** The value here is falsifying
   folklore; an intervention that raises bits is the most useful finding
   available.
4. **Never recommend an untested intervention in this repo.** The failure mode
   is advice that makes the reader more identifiable.

## Still open

- Measuring your own anonymity set requires the population baseline problem to
  be solved first ([Dig 1](01-population-baseline.md)). Until then, intervention
  effects can only be measured as *relative* changes against reference
  distributions, not absolute bits.
- Whether "is a Tor user" or "runs 12 privacy extensions" is itself worth
  measuring as a signal — probably yes, and it belongs in the catalog.

## Sources

- [Sanchez-Rola et al., *To Extend or not to Extend: on the Uniqueness of Browser Extensions and Web Logins*](https://arxiv.org/pdf/1808.07359)
- [Tor Project, fingerprinting protections](https://support.torproject.org/tor-browser/features/fingerprinting-protections/)
- [Laperdrix et al., *Browser Fingerprinting: A Survey*](https://arxiv.org/pdf/1905.01051)
- [Staab et al. 2024, *Beyond Memorization*](https://arxiv.org/abs/2310.07298)
- [Berke et al. 2025 (PoPETs)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §7
