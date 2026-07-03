# VerdictPlane — Review Gate

A lightweight checklist run **before calling any output final** — a release, a paper, a deck, a
report, or an upgrade document. It exists to catch the failure the T7 review caught: claims drifting
ahead of what the code/artefacts actually support. Adapted from external reviewer feedback and scoped
to a software-governance + benchmark project.

Mark items **N/A** where they don't apply to the output type (noted per item).

## Always (every output)

- [ ] **Claims match the artefacts.** Every quantitative claim regenerates from `make bench` /
      `make test` / a committed file, and the wording does not exceed what the mechanism provides
      (e.g. HMAC = *keyed tamper-evidence*, **not** non-repudiation; anchoring covers truncation
      *below the last anchor*).
- [ ] **Honest scope.** Limitations are stated, not hidden. No overclaiming on synthetic results, no
      hidden oracle/label leakage, no "SOTA" without external reproduction.
- [ ] **Metrics are explicitly defined** — name, formula/definition, what it measures, why it matters
      (see [`docs/METRICS.md`](METRICS.md)).
- [ ] **Metric-to-failure mapping is present**, and each metric is tagged *measured / operational /
      planned* so a reader can't mistake a roadmap metric for a measured one.
- [ ] **No forbidden attribution / no secrets** in the diff or commit message (pre-push guard passes).

## Core invariants (code / release outputs)

- [ ] **No model in the enforcement path** (static import allowlist test still green).
- [ ] **Zero egress** (static + runtime socket kill-switch + empty-netns battery still green).
- [ ] **Append-only provenance**; the gate is **fail-safe → deny**; unmatched actions hit the safe
      default.
- [ ] **Reproducibility:** benchmark/evidence captures are commit-pinned; a full run on a clean tree
      regenerates them (`make repro` for a turnkey container).
- [ ] Test count and version strings updated; suite green.

## Method & setup (research outputs: papers, decks — esp. EAG-Bench)

- [ ] **Method** states: inputs, the decision path, what is *deployable* vs *diagnostic*, and what is
      held fixed (seeds, policy, hardware, governor).
- [ ] **Experiment setup**: dataset/split + `source` provenance (synthetic / real / anonymized),
      protocol, baselines, ablations, hardware/software details.
- [ ] **Related work** is *analytical* — grouped by theme with an explicit research gap — not a
      descriptive list.
- [ ] **Corpus integrity** (EAG-Bench): labels reproduce from deterministic policy; an independent
      reviewer validated a sample; per-action rationale and disagreements are published.

## Narrative (decks / talks)

- [ ] Logical flow: **Problem → Evidence → Method → Results → Challenges → Insights**.
- [ ] The single headline claim is stated once, precisely, and is defensible on its own slide.

---

*Keep this gate lightweight. If an item repeatedly doesn't apply, prune it — a checklist nobody runs
is worse than none.*
