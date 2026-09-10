# DECISION — cycle 4: label strategy & calibration (Round 3 synthesis)

2026-09-10. Claude Round 1 + Codex Round 2 + Claude verification. This sets a
development plan. It does NOT change the acceptance gate, the runtime default,
or authorize human labeling beyond what is listed. Two items are marked
**USER DECISION** and are not settled here.

## AGREED (both AIs, verified where checkable)

1. **No bulk human labeling is committed.** Diagnosis first. pilot54 and
   first40 stay unscored for now.
2. **The AI-draft teacher is not proven to be *the* bottleneck.** Claude's
   Round 1 "that is what produced the current ML weakness" is retracted as
   premature. Codex re-ran the 338 / 938 / 3,137 comparison (k=5, bigrams):

   | Training | dev-200 MAE | dev-200 mean rho |
   |---|---:|---:|
   | Full 3,137 | 14.90 | 0.280 |
   | Seed 338 | 17.07 | 0.318 |
   | Seed + accepted NICT 938 | 15.46 | 0.294 |

   Dropping AI drafts helps rank slightly, hurts MAE, and reverses on the
   non-overlap slice. No CI. Does not identify teacher vs capacity vs input.

3. **dev-200 is not a clean holdout.** VERIFIED: 100 of 200 dev rows share a
   canonical training group (AMI 65 / NICT 28 / Taskmaster 7); the other 100
   are AMI 2 / NICT 40 / Taskmaster 58. `gold-holdout` in
   `evaluate_axis_analyzers.py` does not enforce group exclusion. Every
   comparison from here must use a **common training set purged of all
   dev-200 canonical groups** (recover NICT provenance first), membership
   frozen across arms.
4. **AI consensus is never a human label.** An alternative LLM teacher is a
   diagnostic of *this* teacher's bias against the human anchor, not truth.
5. **An independent human evaluation stays required** for any "reads human
   tone better" claim. Minimum for the existing reserved pool: **176 items ×
   5 axes × 2 trained humans = 1,760 scores**, only after model / rubric /
   inputs / comparators / exclusions are frozen. Keep per-scorer ratings;
   never fill a missing rating with a teacher or a consensus.
6. **Calibration != model improvement and != proof of correctness.** It only
   measures whether scorers share an interpretation. Shared bias survives
   perfect agreement.

## DECIDED (this cycle, within existing constraints)

### D1. Calibration shrinks to 30 items x 2 primary scorers (was 4 x 90)

- 10 items per source, the **two intended primary evaluation scorers** in
  slots A/B. Slots C/D are kept for blind adjudication of >20-point gaps; if
  C/D later become primary scorers they first qualify on shared items.
- 30 x 5 axes x 2 = **300 scores** (was 1,800).
- Before regenerating: **fix the sampler** -- `_take_by_hash` currently hashes
  rows and favours larger groups; replace with (i) pick unique groups by a
  seeded hash, then (ii) pick one random utterance within each chosen group.
  Drop the dead `rng.shuffle` in the residual arm (`_take_by_hash` re-sorts
  it).
- **Fix the probability language.** For a fixed A/B pair, a >20-point gap at
  10% prevalence gives `1 - 0.9^10 = 65%` per source, ~28% simultaneous
  across three sources -- not 95%. State it as a screen, not a guarantee. Use
  the hypergeometric form against the actual eligible population, not
  `0.9^n`. Escalate toward 30/source only if a persistent source-specific
  inconsistency shows up.
- **Human-check the rubric examples first.** VERIFIED: 6 of 8 workbook
  examples reproduce seed-dataset scores exactly and the seed labels are
  AI-assisted (gemini/gpt/claude-assisted), not human-verified. Anchoring 4
  reviewers on AI scores defeats the calibration. A human must re-score the
  examples (or replace them) before distribution.
- Calibration still runs **before** first40 (keeps contract section 7 order).

### D2. Two-week diagnosis order (no new human labels in days 1-5)

- **Days 1-3 -- measurement + teacher-fidelity + representation.**
  - Rebuild all comparisons on a dev-group-purged common training set;
    freeze a baseline/exclusion ledger with hashes (experimental training
    SHA-256 `23051000c3c2c4e0c38a876de61973d156188ef151faad69fca18caf20ddc1e9`).
  - Re-run rule / ML / hybrid with original vs decimal targets, unigram vs
    bigram, 338 vs 3,137, per-source and per-reviewer slices, NA-aware.
  - Teacher fidelity: group-held-out split *inside* training; measure how
    well the student reproduces the stored weak labels with no same-group
    neighbours. Separately measure current-`draft_axes` vs stored-label
    mismatch (already have: 221/600, Formality/Energy only, |delta| 2.6/1.1).
  - Representation with labels+texts fixed: k in {3,5,9}, unigram/bigram, and
    one caps/repeated-punctuation ablation **only if** the real transcript/
    STT inputs keep those features (check first).
  - Do NOT spend days on the decimal or dedup hypotheses -- measured effect is
    ~0.006 MAE and there are 0 duplicate utterances.
- **Days 3-5 -- calibration + rubric + alternative teacher.**
  - Run the fixed 30x2 calibration (D1). Inspect every >20 gap, per-axis
    signed and absolute mean gaps, notes. A source-axis signed mean gap > 10
    or repeated >20 gaps -> discuss + fresh shared rescoring before first40.
  - Freeze the current-utterance-only rubric.
  - One frozen `gemini-2.5-flash-lite` protocol (model already used in
    `ai/generate_feedback.py`): structured 5-axis output, explicit anchors in
    the prompt, no buckets / gold / source / model hints, current utterance
    only, low fixed temperature, log everything, reject invalid outputs.
    Score all 200 dev utterances once + 30 group-distinct items (10/source)
    repeated once for instability. Compare its per-axis MAE/bias/rho vs
    human gold to `draft_axes`'s. A small non-evaluation preflight confirms
    account/schema access before the run.
- **Days 6-9 -- bounded first40 (only if calibration prerequisites hold).**
  - Freeze B = chosen baseline rows after dev-group purge (record real row
    count + hash; do not call it "3,137"). No k / mixture retuning after
    this point.
  - 2 independent humans score the same 40 E/C/I items; decimals kept; 3rd
    blind adjudicator for >20 gaps; one aggregated training row per item;
    missing F/H stay missing.
  - Compare B, B+S(automated E/C/I labels), B+S(human E/C/I labels) -- same 40
    texts, identical IDF/vectors/k/rounding; the automated arm is a tagged
    control, never a fill. Keep F/H from B (frozen) so partial-label refit
    does not silently move unreviewed axes.
  - Evaluate on dev-200 with B purged of all its groups: E/C/I macro MAE/rho,
    all three axis deltas, source/reviewer slices, paired group bootstrap
    (95%, 10,000, seed 20260910). Show the non-overlap-100 sensitivity and
    5-axis guardrails vs fixed rule / old hybrid.
- **Days 10-14 -- decide by prespecified rules.**
  - Expand trigger (not a new gate): human vs same-text automated control
    improves E/C/I macro MAE by >=1.0 and macro rho by >=0.05, paired 95%
    intervals exclude no-improvement, no evaluated axis worse by >1 MAE or
    >0.03 rho, and it beats B itself and is not a source/reviewer artifact.
    -> then annotate at most the remaining 80, reassess the curve. Never
    thousands.
  - Stop if gains < 0.2 MAE and < 0.01 rho **and** intervals exclude the
    worthwhile effects. Wide intervals spanning benefit and harm =
    **inconclusive**, not "human labels never help".
  - Only if a model is genuinely ready: freeze everything, hand off 176x2
    independent evaluation (AGREED #5). Otherwise the reserved pool stays
    closed past two weeks. A calendar deadline is not evidence to open it.

### D3. Phase 2 artifact corrections (before any distribution)

- Regenerate calibration at 30x2 with the fixed sampler + probability text +
  human-checked examples.
- pilot54: keep as candidates, **do not distribute**. Its 9-control
  allocation is contingent on the calibration size and frees up when
  calibration shrinks.
- first40 40: keep; add a recorded selection-model provenance (which model /
  data / ngram produced the disagreement scores).
- Fix the decimal path in `_validate_axes` / `_validate_partial_axes` /
  `ml_baseline` validation and `select_ml_transition_annotation_sets` before
  training on reviewer means.
- Fix stale text: contract section 11 "calibration 48"; workbook wording;
  `evaluate_axis_analyzers.py` gold-holdout "frozen" description; add
  group-exclusion enforcement to gold-holdout.
- Keep: stable IDs, per-slot blind manifests, raw/adjudicated separation,
  closed reservations (train-1200 ∩ gold-600 canonical groups = 0, verified).

## USER DECISION (not settled here)

### U1. Strategic goal -- keep the human-gold acceptance gate, or change it?

- **Keep (default):** target "analyses human-perceived tone better", human
  gold gate stays, D1-D3 proceed as written. "Reproduce the teacher" is at
  most an auxiliary diagnostic.
- **Change:** target "reproduces the rule/AI teacher consistently". The
  human-gold gate is void, the evaluation metric changes, calibration and
  the 176x2 eval mostly fall away. This is a real scope change and only the
  user can make it.

### U2. The calibration artifacts already built (4x90 + workbooks, committed `fce9cea`)

- **Rebuild to 30x2 (default, matches D1):** supersede the 4 workbooks; keep
  the 90-row candidate file as the eligible pool.
- **Keep 4x90 as-is:** only if the user wants the stronger per-source screen
  now and accepts 1,800 scores of reviewer time before diagnosis.

## Not doing

- Not opening the reserved final pool.
- Not changing `PALLY_AXIS_ANALYZER`.
- Not scoring pilot54 or first40 before the calibration + rubric gate.
- Not treating any LLM output (single or consensus) as a human label.
- Not committing to any labeling volume beyond first40 (+ its 80 remainder,
  conditionally).
