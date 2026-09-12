# CURRENT TASK — cycle 4d: close remaining B0-B4 open items

## Goal

Close out (or explicitly scope) the items cycle 4c left open, and sanity
check the two things Claude did since: the vocabulary-matched ridge-vs-kNN
ablation, and the post-fix bootstrap. Recommend how to handle B3b's
Formality bias without new dev-200 leakage.

## Round 2 지시 (Codex)

Read `docs/ai-collab/CONTEXT.md`. Using real repo code/data:

1. **Verify the vocabulary-matched ablation.** Claude reports: fitting
   `RidgeAxisRegressor(word_ngram_max=2, min_df=1, max_features=999999)` on
   the same 2,940-row purged training set gives a 17,913-feature vocabulary
   (matching kNN exactly) and dev-200 rho **0.4202**, versus kNN's **0.3624**
   and the capped-vocab (4,000-feature) ridge's **0.4279**. Reproduce this.
   Does matching vocabulary really isolate the estimator-family effect, or
   is there a remaining confound (e.g. TF-IDF weighting details, L2
   normalization, feature ordering, tie-breaking)?
2. **Verify the post-fix bootstrap** in `scripts/bootstrap_b0_b4_comparison.py`
   (commit `6c322ce`). Is the resampling scheme (resample groups with
   replacement within each source, same group count as observed, reuse
   indices across arms) appropriate for this comparison? Any bias in it
   (e.g. does it handle sources with few groups, like AMI's 39, reasonably)?
   If you'd design the interval differently, say how and whether it would
   likely widen or narrow the reported CIs.
3. **Recommend how to handle B3b's Formality bias** (Flash-Lite trained
   labels carry a ~+14 to +18 systematic Formality over-scoring that the
   ridge student reproduces, MAE 15.4-15.6 vs hybrid's 9.6) without
   introducing new dev-200 leakage. Options to evaluate, add your own if
   better:
   (a) leave it uncorrected, report as a known defect, decide later with
       the reserved-176 pool;
   (b) estimate a bias correction from a portion of the ALREADY-scored
       Flash-Lite training pool against something independent of dev-200
       (name a concrete independent anchor if one exists, or say none does);
   (c) split dev-200 itself into a calibration slice and a reporting slice
       (state the cost: dev-200 is already repeatedly analyzed, so this
       adds another use, and shrinks the reporting slice);
   (d) something else.
4. **Given the post-fix bootstrap showing neither ridge candidate beats
   hybrid with 95% confidence, is it premature to build a B3b deployment
   adapter right now?** Recommend proceed / hold, and what evidence bar
   should be cleared first if "hold."
5. **Anything else** a skeptical reader would still flag in
   `docs/ml-transition-diagnosis-log.md` sections 11-12 as currently
   written, or in the committed scripts, before this goes into a report
   shared with the team.

Write to `docs/ai-collab/CODEX_REVIEW.md` ONLY. Do not modify any other
file. Do not commit, push, or reset git state. Do not call any external
API. Do not open the reserved final test pool.
