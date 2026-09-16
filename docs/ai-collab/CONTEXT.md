# CONTEXT — cycle 4d: closing the open items from cycle 4c's B0-B4 review

## Where this sits

Cycle 4c (Codex Round 2, `docs/ai-collab/archive/` will hold it once archived)
adversarially checked the B0-B4 experiment and found real problems, all
verified by Claude against the code/data:

1. Ridge L2 regularization was batch-dependent, not standard -- **fixed** in
   `ai/linear_axis_model.py` (commit `ec04458`). Rerun: ridge(draft) rho
   0.439->0.428, ridge(Flash-Lite) rho 0.480->0.462.
2. The claim "B4 (Flash-Lite live) cannot run in parallel with reply
   generation" is false -- `_call_gemini_chat()` doesn't take the computed
   axes/character, only a stored `character_name` string. **Retracted.**
3. B3b (ridge trained on Flash-Lite labels) inherits Flash-Lite's Formality
   over-scoring almost verbatim: Formality MAE 15.4-15.6 vs hybrid's 9.6.
   **Not fixed.**
4. B1-vs-B3a was not an isolated model-family comparison (ridge capped
   vocab at 4,000 features vs kNN's 17,913). Claude has since re-run ridge
   with the vocabulary matched exactly to kNN's 17,913 features
   (`min_df=1, max_features=999999`): **rho 0.4202** (vs kNN 0.3624, vs the
   capped-vocab ridge 0.4279). The model-family effect survives a matched
   vocabulary. This item is now addressed, pending your check.
5. The quoted B1 number (rho 0.362, k=15/bigram) is the max of a 15-cell
   sweep run directly on dev-200 -- selection-optimistic, unquantified size.
   Claude is running a nested-selection check now (inner group-holdout
   inside the purged training set, select k/ngram there, evaluate once on
   dev-200) -- result pending, will be added to this file or reported
   separately once done.
6. After the L2 fix, Claude reran the source-group-stratified bootstrap
   (script now committed: `scripts/bootstrap_b0_b4_comparison.py`,
   commit `6c322ce`). **New finding, not yet reviewed by you:**

   | Paired difference | Observed | 95% CI |
   |---|---:|---|
   | B3a (ridge, weak labels) - B2 (hybrid) | +0.0197 | [-0.0211, +0.0684] -- crosses zero |
   | B3b (ridge, Flash-Lite labels) - B2 (hybrid) | +0.0542 | [-0.0162, +0.1320] -- crosses zero |
   | B4 (Flash-Lite live) - B3b | +0.0799 | [+0.0299, +0.1341] -- clearly positive |

   **Neither ridge candidate is statistically distinguishable from hybrid
   on this dev-200 bootstrap.** Only the live Flash-Lite call is confidently
   better than what came before it. This is a materially weaker claim than
   the cycle 4c writeup implied even after its corrections.

## Still open (this round's focus)

- **Formality bias in B3b (item 3):** no fix attempted yet. The direct fix
  (subtract a bias estimated from dev-200) would itself be new dev-200
  leakage. Need a recommendation: leave uncorrected and report as a known
  defect, find an independent calibration source, or something else.
- **Nested k/ngram selection result** (item 5): pending, will share once the
  background run finishes.
- **Deployment adapter for B3b:** still doesn't exist. Given item 6's
  bootstrap result, building it now may be premature -- worth your opinion
  on whether it's still worth building given the current evidence.
- **Reviewer/source confound** (from cycle 4c item 9): unresolved by
  available data; likely stays unresolved until a same-text multi-reviewer
  round exists (ties to the still-paused calibration work).

## User's fixed goals (unchanged)

1. Minimize human labeling work.
2. Transition the runtime analyzer to ML.
3. Every step must have a sound, documented justification.

The user has asked Claude to keep iterating with you and flag anything that
needs their explicit approval (methodology choices with real tradeoffs,
not routine execution).

## Files this round may read

- `ai/linear_axis_model.py` (post-fix)
- `scripts/bootstrap_b0_b4_comparison.py` (new, committed)
- `scripts/experiment_b1plus_linear_student.py`
- `docs/ml-transition-diagnosis-log.md` sections 11-12
- `docs/ai-collab/archive/` for prior cycle history if useful
