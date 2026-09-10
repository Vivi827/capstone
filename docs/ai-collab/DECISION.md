# DECISION — cycle 4b: Day 1-3 results, corrections, revised plan

2026-09-11. Claude Round 1 (Day 1-3 diagnosis) + Codex Round 2 + Claude
verification. Development plan only. No gate / runtime / labeling change.

## Corrections to Claude's Day 1-2 claims (Codex caught, Claude verified)

1. **"ML overfits NICT because NICT dominates training" is WRONG.** Verified
   source counts: NICT 600, CHiME 600, AMI 599, HCRC 500, Taskmaster 500.
   NICT is tied-largest at 19.1%, not dominant. Drop the overfitting story.
2. **"the leak was flattering ML on rank" is WRONG direction.** Purging moves
   ML rho +0.004 (better) and MAE +0.069 (worse); hybrid rho also improves.
   The overlap-100 vs clean-100 gap is a source-composition difference
   (clean-100 = Taskmaster 58 / AMI 2; overlap-100 = AMI 65), not a leakage
   effect. Both slices are dev, neither is a test.
3. **"ML does not generalize to Taskmaster" is too blanket.** Verified
   per-axis on Taskmaster: Energy rho ML -0.182 vs rule +0.401 (ML bad), but
   Curiosity rho ML +0.751 vs rule +0.665 AND MAE ML 21.9 vs rule 31.4 (ML
   clearly best). Intimacy MAE ML 27.2 vs rule 15.9 (ML much worse). The
   problem is axis x source specific.
4. **E3 caps ablation is moot.** `ml_baseline._tokenize()` already lowercases,
   and dev-200 has 0 repeated-`!?` rows, 1 row with `!`. Only the punctuation
   part of the STT finding stands.

## What actually holds after Day 1-3

- ML alone on dev-200 (dev-group-purged, bigram, k=5): MAE 14.97 / mean rho
  0.284. hybrid 14.28 / 0.391. rule 14.54 / 0.372. ML is below both on rank.
- The training target for AMI / CHiME / HCRC / Taskmaster **is `draft_axes`
  output verbatim** (verified: rho 1.000, MAE 0.000 reproduction). NICT
  differs on 208/567 rows, Formality/Energy only, mean |delta| 2.6/1.1.
- The student reproduces that deterministic teacher only moderately
  (held-out rho ~0.33 AMI / ~0.46 Taskmaster / ~0.54 NICT). A lexical TF-IDF
  kNN cannot recover a lexical function it trained on beyond ~0.4-0.5.
- **Both teacher and student have problems** (Codex + Claude agree):
  - teacher: source-specific Intimacy over-scoring, verified via
    `bucket_sensitivity` variantB -- teacher minus human Intimacy bias
    AMI +15.6 / NICT +7.3 / Taskmaster +27.8. ML's large Intimacy MAE is
    consistent with inheriting this.
  - student: cannot reproduce even the deterministic teacher well.
- **STT input skew (verified in code, not yet with a real STT sample):**
  `backend/main.py` sets `enableAutomaticPunctuation=False` (both STT call
  sites) and passes the transcript straight to `_analyze_axes`. On
  punctuation-stripped dev-200: rule rho 0.372 -> 0.317, ML 0.284 -> 0.274,
  hybrid 0.391 -> 0.378. The rule path loses ~0.055 rho it keeps in the
  current eval; hybrid-over-rule margin widens 0.019 -> 0.061. This does not
  make pure ML win, but it is a concrete serve-time argument against
  pure-rule.

## DECIDED — revised Days 4-9

### Fixes before any further experiment

- Every split (E1, E4, size curves) must attach a **provenance-recovered
  source-qualified canonical group to each row/example** and assert 0 group
  intersection after splitting. `split_by_source_group`'s empty-group ->
  utterance-hash fallback re-leaks NICT (verified: 14 NICT rows). IDF fit on
  the train part only.
- Freeze a baseline ledger: original training SHA-256
  `23051000...`, dev-200 SHA-256 `7dedff32...`, **and the hash of the
  2,940-row purged artifact once it is written to a file** (not the 3,137
  hash). Record the exact model spec of the fixed rule and the fixed old
  hybrid (rule code version + ML k/ngram + training hash), not just a name.

### Experiment bundle (Days 4-6, no new human labels)

- **E1 (fixed):** provenance-clean group-held-out split inside the purged
  training set. Per source x axis: student-vs-stored, current-`draft_axes`-vs-
  stored, plus the axis constant/median baseline, target variance, bias, and
  NA reason so a narrow-range low MAE is not mistaken for fidelity. NICT
  included but never averaged into one number with the draft/seed rows.
  Reading is "can the current model approximate this held-out weak-label
  distribution", not a single cause for human performance.
- **k/ngram:** k in {3,5,9} x {uni,bi} on the purged set, per source x axis,
  with neighbor diagnostics (neighbor source mix, top-k similarity,
  zero-similarity/OOV rate, label variance). This is a within-TF-IDF search,
  not a verdict on representation.
- **E2:** dropped for non-NICT (verified no-op). NICT: a small controlled
  Formality/Energy offset swap on the 208 differing rows only, texts /
  membership / IDF / k fixed. Not billed as "a better teacher".
- **E4 size curve:** deferred until after the Flash-Lite comparison; only run
  if E1 + teacher comparison leave the scale question open.
- **E5:** target-column variance / uniqueness / nonzero count per source x
  reviewer, and a prespecified near-duplicate rule with a reviewer x source
  cross-tab. No text-only ceiling claim.

### Flash-Lite alternative-teacher comparison (Days 6-8) -- USER PREFLIGHT

- One frozen `gemini-2.5-flash-lite` protocol (model already used in
  `ai/generate_feedback.py` / `backend/main.py`). Structured 5-axis output,
  explicit rubric anchors in the prompt, current utterance only, no gold /
  source / bucket / model hints, low fixed temperature, log everything,
  reject invalid outputs.
- Score all 200 dev utterances once + 30 group-distinct items (10/source)
  repeated once for stability. Compare per-axis MAE / signed bias / rho vs
  the human gold to `draft_axes`.
- **If materially better than `draft_axes` on the axes where ML is weak:**
  relabel a fixed **train-only** subset with Flash-Lite, retrain the student
  with identical representation/k, and compare that deployment candidate to
  the current-label student on dev. The bar is "the distilled student
  improves", not "the teacher improved".
- Dev-generated Flash-Lite scores never enter training.

### first40 (Days 8-9)

- Run the bounded before/after ONLY if the automated path (better teacher ->
  better student) does not clear hybrid on dev. If it does clear hybrid,
  skipping first40 is a plan change to be recorded, and the user decides it
  (see below).

### Deployment-path validation (before any gate)

- `MLAxisAnalyzer()` default = k=5 / unigram / `axis_dataset_week2.jsonl`
  (338 rows) or `PALLY_AXIS_DATASET`. This is NOT the research candidate.
  Before the gate, wire the deployment adapter to the exact frozen artifact
  (purged training file + k + ngram) and verify it, and confirm the
  rule-fallback path is not silently mixing into "ML" outputs.

## USER DECISION POINTS — in order

1. **Flash-Lite preflight (now-ish).** The comparison needs one real
   `gemini-2.5-flash-lite` call to confirm the API key / project / structured
   output work (CLAUDE.md section 4). The model is already in the codebase.
   Decision: proceed with a small preflight call now, or provide / confirm
   the credential first.
2. **U1 after the diagnosis bundle.** Keep the human-perceived-tone gate
   (default) vs change the goal to "reproduce a teacher". E1's result does
   not force this either way.
3. **Execution order after Flash-Lite.** If the automated teacher -> student
   path clears hybrid on dev: skip first40 (record as a plan change) or still
   do bounded first40 for corroboration; when to resume 30x2 calibration
   scoring.
4. **Final-eval protocol, before opening the reserved pool.** Concrete
   CI-based pass / inconclusive rule, tolerances, required axes, scorer
   count, per-set sample sizes. 176 x 2 x 5 = 1,760 scores is the current
   minimum and is not proven sufficient; a smaller confirmatory design needs
   a prospective power argument and explicit approval.
5. **Runtime switch.** After a frozen candidate passes `final_gate` and
   reproduces on `gate4_reproduction`, with the deployment adapter verified
   and regression-vs-rule reported: explicit approval to set
   `PALLY_AXIS_ANALYZER`. Statistical uncertainty = not a pass.

## Not doing

- Not opening the reserved final pool.
- Not changing `PALLY_AXIS_ANALYZER` or the gate.
- Not scoring calibration / pilot / first40 yet.
- Not treating any LLM output (single or consensus) as a human label.
- Not committing to a labeling volume beyond a possible bounded first40.
