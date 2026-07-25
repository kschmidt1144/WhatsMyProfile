# Research notes

Eight digs into the literature underlying this lab, done 2026-07-25. Each note
records what was verified, what it changes in this repo, and what remains open.

Figures here were checked against primary sources at the time of writing;
where a result is contested, the critique is recorded alongside it.

| # | Dig | The one thing that changed |
|---|---|---|
| [01](01-population-baseline.md) | Population baseline | Entropy measured on a sample of N cannot exceed log₂(N). Every published figure we cite is a sample-capped lower bound, and our headline number was computed against the wrong denominator. |
| [02](02-adversary-model.md) | Adversary model | LINDDUN separates *linkability* from *identifiability*. So must we — they are different threats with different mitigations. |
| [03](03-k-anonymity-and-dp.md) | k-anonymity and DP | Our bits framework composes like differential privacy, not like k-anonymity. That is a strength, and it names the correction we need. |
| [04](04-behavioral-traces.md) | Behavioral traces | 4 spatio-temporal points identify ~95% of people. Static attributes are the small half of the problem — and sample uniqueness ≠ reidentification. |
| [05](05-linkage.md) | Linkage | Uniqueness is worthless to an attacker without an identified source to link against. Linkage is a separate, necessary step we do not model. |
| [06](06-inference-gap.md) | Inference gap | LLM agents now beat hand-tuned classical de-anonymization. Digs 5 and 6 are the same threat. |
| [07](07-consequence.md) | Consequence vs accuracy | Broker profiles are frequently *wrong* — male gender segments ~42.5% accurate — and operative anyway. Accuracy and effect are independent axes. |
| [08](08-countermeasures.md) | Countermeasures | Hardening often raises identifiability. Uniformity beats randomization. Text anonymization does not defeat LLM inference. |

## The through-line

Three of these digs independently landed on the same correction: **this lab was
measuring the wrong thing in the wrong units against the wrong denominator.**

- Dig 1: entropy figures are capped by sample size, so they are floors.
- Dig 4: sample uniqueness does not imply population uniqueness.
- Dig 5: population uniqueness does not imply reidentification.

Each step is a real reduction in what "you are identifiable" can honestly mean.
Together they say that a bits number, on its own, overstates exposure unless
the sample, the population, and the linkage path are all stated with it. That
correction is now enforced in `entropy.py` rather than left to the reader.

The opposite correction also appeared. Digs 6 and 7 show the *practical* barrier
to exploitation collapsing — LLM agents automate what used to need a specialist,
and the industry acts on profiles it knows are inaccurate. So the theoretical
overstatement and the practical understatement do not cancel; they apply to
different questions. "How identifiable am I in principle?" is smaller than this
lab first implied. "How exposed am I in practice?" is larger.
