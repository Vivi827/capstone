# CURRENT TASK — cycle 4c: adversarial check of the B0-B4 experiment

## Goal

The user is about to receive a written experiment report (for teammates, to
decide whether/how to move off `PALLY_AXIS_ANALYZER=rule`). Before that
report is finalized, get an independent adversarial check on the B0-B4
results in `docs/ai-collab/CONTEXT.md` -- the same role Codex has played in
every prior cycle of this diagnosis (cycle 4 and 4b), which twice caught
real errors in Claude's own claims.

## Round 2 지시 (Codex)

Read `docs/ai-collab/CONTEXT.md`. Then, using the actual repository code and
data (re-run scripts or compute in memory, don't take numbers on faith):

1. **Reproduce the headline numbers.** Re-derive B0/B1/B2/B3a/B3b/B4's
   dev-200 mean rho and MAE (or as many as you can within reasonable time).
   Flag any that don't match `docs/ai-collab/CONTEXT.md`'s table.
2. **Check for leakage or double-dipping specific to B3/B4:**
   - Did any Flash-Lite training label for B3b get generated from a text
     that also appears in dev-200 (should be impossible since training is
     dev-group-purged, but verify against the actual purged file, not the
     claim)?
   - `ai.linear_axis_model.RidgeAxisRegressor`'s hyperparameters (l2, lr,
     epochs, batch_size, min_df, max_features) -- were any of them tuned by
     looking at dev-200 performance, even implicitly? If so, say exactly
     which result is dev-tuned versus a priori.
   - Is the k/n-gram sweep quoted for B1 selected as the best of several
     dev-200 runs? If so, the quoted B1 number is a selected maximum, not an
     unbiased estimate -- say by how much that likely inflates it.
3. **Check the ridge model's legitimacy.** Is `RidgeAxisRegressor` actually
   a defensible ridge regression (correct gradient, actual L2 term, sane
   convergence), or does it have a bug that happens to produce a plausible
   number? Inspect `ai/linear_axis_model.py` directly.
4. **Check the "0 per-turn inference calls" and latency claims for B3b.**
   Confirm B3b's deployed form really requires zero live model/API calls at
   serve time, and that nothing in `ai/linear_axis_model.py` secretly
   depends on scipy/numpy/sklearn (the project's ML baseline is meant to be
   dependency-free).
5. **Check statistical strength.** With n=200 (and often fewer once NA axes
   are dropped, e.g. Humor), how much should one trust a rho difference like
   0.408 (B2) vs 0.480 (B3b)? Is there any confidence-interval or
   bootstrap evidence already in this codebase's history that bears on this,
   and if not, say plainly that the ranking above is a point estimate on a
   repeatedly-analyzed dev set, not a confirmed result.
6. **Anything else a skeptical reviewer would flag** before this goes into a
   report used to decide production behavior -- overclaiming in the writeup,
   missing per-axis nuance (e.g. an arm winning "on average" while losing on
   a specific important axis), source-composition confounds, or terminology
   that overstates certainty.

Write findings to `docs/ai-collab/CODEX_REVIEW.md` ONLY. Do not modify any
other file. Do not commit, push, or reset git state. Do not open the
reserved final test pool. Do not call any external API (dev-200 and the
training pool are already scored; use the existing files).
