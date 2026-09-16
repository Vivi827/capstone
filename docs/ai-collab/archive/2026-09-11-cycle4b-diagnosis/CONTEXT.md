# CONTEXT — human-labeling scale & calibration necessity (2026-09-10, cycle 4)

## The question on the table

Codex recommended: do NOT pre-commit to large-scale human labeling. Automate
training labels (LLM / weak supervision), keep human effort to a small
independent eval set + hard-case adjudication, and don't treat the 4x90
calibration as automatically necessary. Diagnose *why* ML is behind before
deciding label volume.

Claude's earlier framing overstated the case ("ML low => hundreds/thousands
of human labels needed"). That is retracted.

This cycle decides the concrete execution order and whether/how much
calibration runs now.

## What is already built and committed (branch gsd/phase-ai-ml-transition-execution)

- `ai/ml_baseline.py`: partial-label support (`_validate_partial_axes`,
  `label_source`, `predict_partial`, `fit(require_full_axes=True)`).
- `ai/evaluate_axis_analyzers.py`: `--mode gold-holdout`, NA-aware means,
  `best_by_spearman` withheld when any required axis rho is NA.
- `scripts/reserve_ml_transition_final_pool.py`: reserved final test pool
  (176 rows / 156 groups, `final_gate` 106 + `gate4_reproduction` 70),
  fail-safe abort before overwrite on provenance/hash mismatch.
- `scripts/diagnose_gold_vs_ai_draft.py`: teacher-vs-gold diagnosis,
  bucket-assumption caveat, NA reporting.
- `scripts/bucket_sensitivity_gold200.py`: generic vs NICT `classify_bucket`
  disagree 132/600 training rows; `draft_axes()` fails to reproduce stored
  NICT labels on 221/600; default-bucket assumption moves Intimacy rho
  0.09 -> 0.29 on dev-200.
- batch review CSV schema (`annotation_batch` / `item_id` / `reviewer_slot`),
  per-slot blind export + manifest, `scripts/aggregate_axis_reviews.py`
  (raw immutable, adjudication overlay).
- Phase 2 candidate sets (UNSCORED): calibration 90 (30/source),
  pilot 54 (event 13 + ami_nonlaugh_control 9 + disagree 16 + residual 16),
  first40 40 (fixed reason x source allocation).
- calibration scoring workbooks for 4 reviewers (slot A-D), same 90 items,
  different order per slot.

## Standing constraints (do not violate)

- Do NOT change `PALLY_AXIS_ANALYZER` default from `rule`.
- Do NOT fabricate/synthesize human labels; do NOT fill unreviewed axes with
  AI drafts.
- Do NOT change the ML acceptance gate or its goal without explicit user
  approval. Surfacing a goal change as an option is fine; deciding it is not.
- `data/fixtures/ml_transition_reserved_final_test_pool.jsonl` stays closed
  until model + analysis plan are frozen. dev-200 and the Phase 2 batches are
  dev only.
- No new runtime dependencies. openpyxl is dev-tooling only.

## Key empirical facts established this project

- gold-200 human review: rule MAE 14.54 / Sp 0.37, ML 14.90 / 0.28,
  hybrid 14.26 / 0.39. ML is behind hybrid AND behind rule on rank.
- The AI-draft "teacher" (`draft_axes`) is demonstrably imperfect: does not
  reproduce its own stored NICT labels (221/600), bucket classifier
  disagreement (132/600).
- Train reservoir (1,200) shares zero canonical group with the gold
  reservoir, so the reserved test pool cannot leak into calibration/pilot.
- AMI is the only source with real event annotations (laughter). Only 13
  laughter groups survive after excluding train-120 + reserved groups.
