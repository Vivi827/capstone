# CONTEXT — cycle 4c: B1+ ridge-on-Flash-Lite-labels experiment review

## Where this sits

Cycle 4 decided: diagnose before committing to bulk human labeling. Cycle 4b
ran Days 1-5 (dev-200 group-purge, teacher-fidelity, STT skew, k/ngram sweep,
Flash-Lite-as-teacher comparison), corrected 3 of Claude's own overclaims
along the way, and after a reviewer-01 Humor re-review, landed on:

  rule 0.344 < pure kNN ML 0.362 < hybrid 0.408 < ridge(draft labels) 0.439
  < ridge(Flash-Lite labels) 0.480 < Flash-Lite called live 0.542
  (dev-200 mean Spearman rho, dev-group-purged training, NA-aware)

This cycle (4c) is a fresh adversarial check specifically on the newest
experiment -- B0-B4 below -- before it goes into a report the user will
share with teammates to make a real decision (whether to move off `rule`,
and to what).

## User goals (fixed, ranked)

1. Minimize human labeling work.
2. Transition the runtime analyzer to ML.
3. Every step must have a sound, documented justification.

## The B0-B4 experiment under review

All on the SAME held-out set (`ml_transition_gold_human_200.jsonl`, 200 rows,
dev-group-purged training so no canonical group in dev-200 appears in
training -- NICT provenance recovered via `source_line` first). All
comparisons NA-aware (Spearman undefined when a target column is constant is
reported as n/a, never averaged in as 0).

- **B0 — rule-based baseline.** `ai.analyzers.RuleBasedAxisAnalyzer`. No
  training data.
- **B1 — nearest-neighbor regressor on the existing weak labels.**
  `ai.ml_baseline.TfidfKnnAxisRegressor` (k=15, word bigrams), trained on the
  2,940-row dev-purged slice of `axis_dataset_combined_real_speech_experimental.jsonl`.
  The weak labels for AMI/CHiME6/HCRC/Taskmaster in that file are the
  deterministic output of `scripts/draft_label_nict_jle_candidates.py::draft_axes()`
  verbatim (verified rho 1.000 / MAE 0.000 reproduction on a held-out split);
  NICT differs on 208/567 rows (Formality/Energy only, human-edited).
- **B2 — hybrid.** Per-axis average of B0 and B1.
- **B3 — a dependency-free ridge (L2-regularized linear) regressor**,
  `ai.linear_axis_model.RidgeAxisRegressor`, same TF-IDF feature pipeline as
  B1, trained by mini-batch SGD (no numpy/sklearn). Run twice:
  - B3a: trained on the SAME weak labels as B1 (`draft_axes` provenance).
  - B3b: trained on labels from B4 (below) instead.
- **B4 — a large language model called directly as a scorer**,
  `gemini-2.5-flash-lite` via `scripts/flash_lite_axis_teacher.py`, one frozen
  prompt (explicit 0-33/34-66/67-100 anchors per axis, current utterance only
  as quoted data, temperature 0, JSON schema enforced, invalid output
  rejected not back-filled). Scored dev-200 directly (200 calls) AND the
  2,940-row purged training pool once (for B3b), never using dev labels to
  tune the prompt.

Also measured: a group-held-out fidelity check inside training (does B1
reproduce the deterministic weak-label function it was trained on?), a
punctuation-stripped/lowercased replay of dev-200 (production STT sets
`enableAutomaticPunctuation=false`), and a k/n-gram sweep for B1.

## Results table (dev-200, mean Spearman rho / mean absolute error)

| Arm | rho | MAE | Per-turn inference calls |
|---|---:|---:|---|
| B0 rule | 0.344 | 12.53 | 0 |
| B1 kNN (weak labels) | 0.362 | 13.21 | 0 |
| B2 hybrid (B0+B1)/2 | 0.408 | 12.36 | 0 |
| B3a ridge (weak labels) | 0.439 | 12.59 | 0 |
| B3b ridge (Flash-Lite-derived labels) | 0.480 | 11.89 | 0 |
| B4 Flash-Lite (live scorer) | 0.542 | 11.00 | 1 (adds serial latency; axis result feeds the reply-generation prompt so it cannot fully parallelize with reply generation in the current pipeline) |

Per-axis rho, per-source rho, and the full method for each arm are in
`docs/ml-transition-diagnosis-log.md` sections 2 and 11-12 (being extended
with the B3/B4 write-up now) and in the commit messages listed in section 7
of that file.

## Known caveats already on record (do not re-litigate unless new evidence)

- dev-200 is a dev/diagnosis set, not the frozen acceptance test. The frozen
  test is `data/fixtures/ml_transition_reserved_final_test_pool.jsonl`
  (176 rows / 156 groups: NICT 70, Taskmaster 105, AMI 1 reference-only),
  unopened, unscored.
- reviewer-01's 100 rows (gold-0101..0200) were re-scored on 2026-09-11
  AFTER seeing the diagnosis (label_status=research_guided_rereview, not
  blind). reviewer-avg's 100 rows are the original blind review.
- Humor is at or near a constant 0 for Taskmaster (65 rows) and for
  reviewer-01's slice broadly (confirmed genuine after re-review, not a
  scoring omission) -- Humor rho is frequently NA or unstable.
- B3/B4 hyperparameters (k, ngram, ridge l2/lr/epochs/batch) were fixed a
  priori from defaults / the k/ngram sweep on dev-200 itself (dev-200 IS the
  dev set, this is allowed use, but it means these are not independently
  confirmed on unseen data yet -- that is what the reserved 176 is for).
- No data from the reserved 176-row pool was used anywhere in this cycle.

## Task for this round

Adversarially check the B0-B4 experiment and the numbers above before they
go into a shared report. Verify against the actual repo code/data rather
than trusting the summary. Flag anything that would embarrass the team if a
skeptical reader found it after the report was shared.
