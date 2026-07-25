# Dig 4 — behavioral traces and trajectory entropy

**Question.** We measure a static attribute vector. Is that where the
information actually is?

No. It is the small half.

## The results

**Mobility** (de Montjoye et al. 2013, *Scientific Reports*): 1.5M people, 15
months of carrier data, location at antenna resolution, hourly.

- **4 spatio-temporal points uniquely identify ~95%** of individuals.
- 2 points still uniquely characterise >50%.
- Uniqueness decays only as roughly the **1/10 power of resolution** — coarsening
  the data buys far less anonymity than intuition suggests.

**Credit cards** (de Montjoye et al. 2015, *Science*): 1.1M people, 3 months.

- **4 spatio-temporal points reidentify 90%**.
- Knowing a transaction's **price raises reidentification risk by ~22%**.
- Women were more reidentifiable than men.

Compare against static attributes: the entire 13-attribute browser fingerprint
in [Dig 1](01-population-baseline.md) measured 12.101 bits jointly. Four
timestamped locations do more work than everything a browser volunteers.

The reason is sparsity. High-dimensional behavioural data is nearly empty —
almost no two people share a trajectory — so a handful of points lands in a
cell occupied by one person. This is the same property Narayanan and Shmatikov
exploited in [Dig 5](05-linkage.md).

## The critique, which we adopt

Sánchez and Domingo-Ferrer's comment in *Science* argues these figures overstate
reidentification risk, on grounds that apply directly to our code:

1. **Sample uniqueness ≠ population uniqueness.** Being unique within a
   non-exhaustive sample does not make you unique in the population. Assuming
   otherwise overestimates risk.
2. **Population uniqueness ≠ reidentification.** The attacker still has to link
   the unique record to an *identified* external source — an electoral roll, a
   customer database. Uniqueness alone identifies nobody.
3. The 1.1M-customer database was a fraction of an undisclosed country's
   population, so sample-to-population inference was doing unacknowledged work.
4. The "anonymisation" compared against was weak and unreferenced, ignoring
   decades of disclosure-control literature.

Point 1 and point 2 are corrections this lab needed. `anonymity_set()` divides
world population by 2^bits, where the bits came from samples of thousands —
committing exactly error 1. And nothing in the schema represents the linkage
step that error 2 insists on.

The critique does not make trajectories safe. It makes the *chain* explicit:
sample-unique → population-unique → linkable → identified, with attrition at
every arrow. We should model the chain, not the first link alone.

## We are already doing this, badly

The GitHub connector's timezone inference is a trajectory inference: a sequence
of timestamped events, aggregated into a 24-bin histogram, read for structure.
It found a real behavioural signature (a sleep window) and mapped it to an
attribute the subject never disclosed.

But `signals` stores it as 19 unrelated rows of `github/push_hour_utc`. The
*sequence* — the thing carrying the information — exists nowhere in the schema.
It was reconstructed in Python and thrown away.

## Decisions taken

1. **Traces become first-class.** A `traces` concept: an ordered set of
   timestamped events belonging to one identity, with its own uniqueness
   measurement, rather than N independent signals.
2. **Implement the attrition chain** rather than a single bits number:
   sample-unique → population-unique → linkable → identified.
3. **Record `sample_n` alongside every uniqueness claim** (also [Dig 1](01-population-baseline.md)),
   so sample and population uniqueness are never silently conflated.
4. Treat **k points from a trace** as the natural unit — "how many observations
   until unique" is the comparable, resolution-independent metric.

## Still open

- Collecting real mobility or transaction traces on oneself is possible
  (Google Location History, bank exports) and is the highest-yield ambient data
  available. It is also the most dangerous thing this repo could hold — see the
  gitignore rules and think hard before enabling it.
- The 1/10-power decay law should be re-derived on our own data rather than
  cited, if traces are ever collected.

## Sources

- [de Montjoye et al. 2013, *Unique in the Crowd* (Sci Rep 3:1376)](https://www.nature.com/articles/srep01376)
- [de Montjoye et al. 2015, *Unique in the shopping mall* (Science 347:536)](https://www.science.org/doi/10.1126/science.1256297)
- [Sánchez, Martínez, Domingo-Ferrer 2016, Comment (Science 351:1274)](https://www.science.org/doi/10.1126/science.aad9295) ·
  [preprint](https://arxiv.org/pdf/1511.05957)
