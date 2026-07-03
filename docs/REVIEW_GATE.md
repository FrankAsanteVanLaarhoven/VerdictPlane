# VerdictPlane — Review Gate

VerdictPlane's instantiation of the portfolio-wide **Mandatory Research Review Gate**. Run before any
output — release, paper, deck, report, upgrade document — is marked final.

Items tagged **(embodied)** apply to robotics / physical-deployment outputs and are **N/A for
VerdictPlane** (a software governance library — no robot, simulator, or physical deployment). Items
tagged **(thesis)** apply to PhD-framing outputs.

**First principle (the T7 lesson): a claim must not exceed what the code / artefacts prove.**

## 1 · Evaluation metrics
Each metric explicitly defined — name, formula/operational definition, what it measures, why it
matters, **how it is computed**, and whether it is **deployable** (runtime cost), **diagnostic**
(verification), or both. See [`docs/METRICS.md`](METRICS.md).
- [ ] every reported metric is there with all six fields
- [ ] measured / operational / planned status is explicit

## 2 · Metric-to-failure mapping
- [ ] every metric maps to the failure it exposes, the claim it **supports**, and the claim it **limits**
- [ ] no roadmap metric is presented as measured

## 3 · Method description
- [ ] inputs, outputs, and the policy / decision path are stated
- [ ] what is held fixed vs what varies between variants
- [ ] what is **deployable at runtime** vs **diagnostic-only**
- [ ] where oracle / label leakage is prevented — for VerdictPlane this is the
      **no-model-in-enforcement** static guarantee (the decision cannot consult a model, so it cannot
      leak a label)

## 4 · Experiment setup
- [ ] corpus / dataset, split, and per-action `source` provenance (EAG-Bench)
- [ ] hardware / software, and the **CPU governor** for any latency claim
- [ ] baselines, ablations, thresholds, evaluation protocol
- [ ] reproduction commands / evidence path (`make repro`; commit-pinned artefacts)
- [ ] **(embodied — N/A here)** simulator or physical environment; robot / device platform

## 5 · Related work
- [ ] analytical, grouped by theme — not a list (cf. README "How VerdictPlane compares")
- [ ] per theme: what it solves, representative work, what it does *not* address, how this differs
- [ ] the research gap is stated and its importance justified

## 6 · Failure, iteration, research process
Show the real path, not a clean-room story:
hypothesis → design → initial results → failures / challenges → refinement → further experiments →
insights → conclusions.
- [ ] failed attempts, blocked claims, and lessons are recorded — e.g. "non-repudiation" blocked down
      to *keyed tamper-evidence*; the benchmark cold-run spread found and fixed; the allow-path
      provenance gap surfaced and closed with an opt-in strict mode

## 7 · Claim boundary
Every claim scoped. Check for:
- [ ] no oracle / privileged information behind a deployable claim
- [ ] no benchmark-wide claim from a small diagnostic split
- [ ] no invented result without a regenerable log / artefact
- [ ] no "safety solved" / "unbreakable" language
- [ ] no overclaiming beyond the evidence — HMAC ≠ non-repudiation; anchoring = truncation *below the
      last anchor*; "standard-setting" not "SOTA" before external reproduction
- [ ] **(embodied — N/A here)** no simulation result presented as physical-deployment proof

## 8 · Slides / talks
Narrative: Problem → why it matters → evidence of failure → metric-to-failure mapping → method →
setup → results → failures / challenges → refinements → insights → next steps.
- [ ] one precise headline claim, defensible on its own slide
- [ ] **(thesis)** three-paper route + next steps where the output is PhD-framing

---
*Keep it lightweight — prune items that don't get used. The portfolio-wide version is the working
standard; this file is VerdictPlane's tailored instantiation.*
