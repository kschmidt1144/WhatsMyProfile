# Dig 6 — the inference gap and its prior art

**Question.** The inference gap is this project's novel claim. Is it novel, and
how would you measure it rigorously?

It is not novel. It is two years old, well-studied, and the results are worse
than this repo assumed.

## Staab et al. — inference from text

*Beyond Memorization: Violating Privacy Via Inference with Large Language
Models* (ETH Zürich SRI Lab, ICLR 2024). The first comprehensive study of
pretrained LLMs inferring personal attributes from text, built on a dataset of
real Reddit profiles.

- Infers location, income, sex and more at up to **85% top-1** and
  **95.8% top-3** accuracy.
- At roughly **1/100th the cost** and **1/240th the time** of human analysts.
- Also demonstrates privacy-invasive chatbots that extract personal information
  through seemingly benign questions.
- **Text anonymisation and model alignment are both currently ineffective** as
  mitigations — see [Dig 8](08-countermeasures.md).

The framing matters: privacy research on LLMs had focused on extracting
*memorised training data*. The threat that turned out to matter is inference at
runtime on text the model has never seen. Nothing needs to leak for you to be
profiled.

## InferLink — inference as de-anonymization

*From Weak Cues to Real Identities* (2026) goes further, and this is the result
that reorganises our roadmap. LLM agents extract scattered contextual clues,
cross-reference sparse anchors across sources, and synthesise weak signals into
an identity hypothesis.

On the Netflix Prize setting at maximum sparsity (2 corrupted data points):

| Method | Identities reconstructed |
|---|---|
| Hand-tuned classical algorithm (the 2008 baseline) | 56.0% |
| GPT-5 agent | **79.2%** |

**A general-purpose agent beat the specialist attack that defined the field.**

Susceptibility varies sharply by model and by framing. Under implicit, benign
task framing Claude 4.5 reached 70–80% linkage success; under explicit
re-identification requests with membership knowledge it reached ≥98%. GPT-5 was
more conservative implicitly (25–45%) but comparable explicitly (80–95%). Worth
recording plainly: the models are not equally resistant, and benign framing does
not make the capability go away.

The ChatGPT-log case study is the bits framework made visible:

> ~300 candidates → **10** (role + research topic) → **2** (publication cues) →
> **1** (temporal career cross-referencing)

That is an anonymity set collapsing by roughly 4.9, then 2.3, then 1 bit. No
single cue was identifying. The combination was.

The authors' conclusion is the one to adopt: identity inference, not just
information disclosure, should be a first-class privacy risk. The historical
protection was never that linkage was impossible — it was that it required
labour and specialist expertise. That barrier is gone.

## Digs 5 and 6 are the same threat

Classical record linkage ([Dig 5](05-linkage.md)) needed structured, overlapping
fields and a specialist to tune the matcher. LLM agents combine unstructured,
heterogeneous, individually-worthless cues with no domain engineering. The
linkage half and the inference half of this project were separated on the
assumption they were different attacks. They are one attack now, and the roadmap
merges them.

## The self-referential problem

This repo ships an MCP server that hands a language model a queryable database
of one person's profile signals. That is, structurally, the InferLink threat
model with the evidence pre-collected and indexed.

The mitigation is that the subject is the operator and the data never leaves the
machine — which is exactly what makes the scope line in the README load-bearing
rather than decorative. Worth stating explicitly rather than discovering later.

## Measuring it properly — the protocol

Borrowed from Berke et al. and Staab et al. rather than invented:

1. **Held-out ground truth.** Attributes the subject knows and the model is not
   shown. Without this, `verdict` stays `unverifiable` forever, as it is today.
2. **Accuracy against base rate, via AUROC.** Berke report AUROC per demographic
   from browser attributes alone: gender .663/.679, Black .677, Asian .698,
   age 55+ .644, income <$50k .605. All above chance, none impressive alone —
   the point is that they *compose*.
3. **Normalised mutual information**, `I(A;D)/H(D) = 1 − H(D|A)/H(D)`, per
   attribute per target. Berke's key structural finding: `Platform` has low
   uniqueness but relatively high MI for gender and age. **An attribute can be
   near-useless for identification and valuable for inference.** Our schema
   must score both, or it will call such attributes harmless.
4. **Multi-model agreement as a recoverability score.** Where independent models
   converge on an undisclosed attribute, it is genuinely recoverable rather than
   one model's hallucination. (Same ethos as the World Economy Lab's panel.)

## Decisions taken

1. Score **inference risk separately from identification risk** — they decouple,
   demonstrably.
2. Add **ground-truth capture** so `verdict` becomes measurable. Store it as
   locally as possible; it is the most sensitive data in the project.
3. Use **AUROC vs base rate** and **normalised MI** as the metrics, not accuracy.
4. Merge the linkage and inference phases in the roadmap.

## Still open

- Storing ground truth to score inference creates a richer dossier than the one
  being studied. This is a real ethical tension, not a solved problem, and it
  may argue for scoring interactively and never persisting.

## Sources

- [Staab, Vero, Balunović, Vechev 2024, *Beyond Memorization* (ICLR)](https://arxiv.org/abs/2310.07298)
- [*From Weak Cues to Real Identities: Inference-Driven De-Anonymization in LLM Agents* (2026)](https://arxiv.org/abs/2603.18382)
- [*Automated Profile Inference with Language Model Agents* (2025)](https://arxiv.org/abs/2505.12402)
- [Berke et al. 2025 (PoPETs)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §7.1–7.2
