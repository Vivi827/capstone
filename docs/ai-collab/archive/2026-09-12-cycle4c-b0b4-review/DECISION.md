# DECISION — cycle 4c: B0-B4 experiment corrected (Round 3 synthesis)

2026-09-12. Claude Round 1 (self-audit) + Codex Round 2 (adversarial check,
re-ran the experiment, computed an exploratory bootstrap) + Claude
verification and one code fix. This corrects the B0-B4 results before they
go into any shared report. It does not change the runtime, the gate, or
authorize opening the reserved pool.

## What Codex found and Claude verified (all confirmed against real code/data)

1. **CONFIRMED — the ridge regularizer was non-standard.**
   `ai/linear_axis_model.py` applied the L2 shrinkage only to features
   present in the current mini-batch, so rare features were shrunk far less
   than frequent ones per step (not a property of ridge regression). Fixed:
   L2 decay now applies to every weight every step
   (`ai/linear_axis_model.py`, commit pending). Rerun after the fix:
   ridge(draft) rho 0.439 -> 0.428, ridge(Flash-Lite) rho 0.480 -> 0.462.
   Both still clear hybrid's 0.408; the fix changes the number, not the
   ranking, for this dev-200 snapshot.

2. **CONFIRMED — B4 (Flash-Lite) is not actually blocked from running in
   parallel with reply generation.** Claude's claim that "the axis result
   feeds the reply-generation prompt" is false in the current code:
   `_call_gemini_chat()` (`backend/main.py:694`) takes only
   `character_name` (a stored string, e.g. "Pally") and `level`, not the
   computed axes or `character` dict. There is no code today that makes
   axis scoring and reply generation sequential by data dependency -- they
   are sequential only because no one has written them to run concurrently.
   An async implementation is still unbuilt and unmeasured; "cannot fully
   parallelize" is retracted. "Cost of one more API call per turn either
   way" stands.

3. **CONFIRMED, IMPORTANT — B3b (ridge on Flash-Lite labels) inherits
   Flash-Lite's Formality bias almost verbatim.** Verified directly:
   Formality MAE 15.4-15.6 for B3b vs 9.6 for hybrid (B2) -- a large
   regression the pooled mean-rho number hides completely. Cause: Flash-Lite
   over-scores Formality by roughly +14 to +18 on dev-200 (already known
   from the Day 5 write-up), and since ridge is trained to reproduce
   Flash-Lite's training labels, it reproduces that same additive offset on
   new text. This is expected behavior for a regression trained on biased
   labels, not a new implementation bug. It is NOT fixed by the L2 correction
   above. **Not fixed in this cycle** -- a bias correction would need to be
   calibrated on data other than dev-200 itself to avoid new dev leakage.
   Report this as an open problem, not a solved one.

4. **CONFIRMED — B1 -> B3a does not isolate "model family" alone.**
   `RidgeAxisRegressor` caps vocabulary at 4,000 features (`min_df=2`);
   `TfidfKnnAxisRegressor` on the same data keeps 17,913. The two arms differ
   in vectorization/vocabulary as well as estimator. B3a vs B3b (same
   linear implementation, only the labels differ) IS a clean isolated
   comparison; B1 vs B3a is not. Report "this linear pipeline beats this kNN
   pipeline on dev", not "capacity increase, isolated".

5. **CONFIRMED — the quoted B1 number (and the k=15/bigram choice reused for
   B3a/B3b/hybrid) is the maximum of a 15-cell sweep run on dev-200 itself.**
   Codex recomputed all 15 cells: k5/unigram gives 0.297, k5/bigram gives
   0.288, k15/bigram (quoted) gives 0.362. The gap between the quoted number
   and an unselected default config is real but the SIZE of the selection
   optimism cannot be estimated from this sweep alone (would need a nested
   held-out selection or a frozen independent evaluation). Report the
   sweep-max framing explicitly; do not call 0.362 an unbiased estimate.

6. **CONFIRMED — the full ranking is NOT stable across the two dev-200
   snapshots analyzed this week.** Before the reviewer-01 re-review
   (commit `255a332`): best kNN rho 0.350 < rule 0.372. After the re-review
   (commit `4f809db` onward): kNN 0.362 > rule 0.344. Same texts, revised
   labels on 100 of the 200 rows -- this is not two independent replications,
   it is the same dev set analyzed twice with a nonblind label revision in
   between. Do not describe the ranking as replicated across independent
   states.

7. **NEW — exploratory exact bootstrap (Codex, in-memory, not yet
   committed as a script), on the fixed predictions, group-stratified by
   source (161 groups: AMI 39 / NICT 61 / Taskmaster 61), 1,000 resamples,
   seed 20260912:**

   | Paired mean-rho difference | Observed | Exploratory 95% percentile interval |
   |---|---:|---:|
   | B3b (pre-fix) − B2 | +0.072 | [+0.001, +0.149] |
   | B4 − B3b (pre-fix) | +0.062 | [+0.012, +0.115] |

   B3b's improvement over hybrid is NOT clearly separated from zero at the
   lower end. This interval does not account for repeated dev analysis,
   configuration selection, the nonblind relabeling, or rubric uncertainty --
   it is a development-stage signal, not a confirmatory result. Needs
   re-running against the post-L2-fix predictions before it goes in a report
   (numbers above are pre-fix; direction is expected to hold, magnitude
   unconfirmed).

8. **CONFIRMED — no deployment path exists for B3b today.**
   `ai/analyzers.py`'s `get_axis_analyzer()` supports only `rule` / `ml`
   (kNN) / `hybrid`. There is no ridge serialization/loading adapter. "Ships
   as-is" overstated implementation status; an adapter is unbuilt work, not
   a formality.

9. **CONFIRMED — reviewer/source confound in the B3b gain.** B3b-over-B2
   mean-rho gain is +0.093 on reviewer-avg's rows (AMI+NICT, original blind
   review) vs +0.231 on reviewer-01's rows (NICT+Taskmaster, nonblind
   re-review). The gain is not confined to the revised labels, but the
   reviewer-slice split is confounded with source, so a "reviewer effect"
   cannot be separated from a "source effect" from this alone.

10. **Per-axis regressions beyond Formality** (Codex's table, reproduced):
    Energy rho: B0 rule 0.505 > B2 hybrid 0.426 > B3b 0.389 -- rule remains
    best on Energy specifically. AMI mean MAE: B0 11.76 is best; every ML
    arm (B1/B2/B3a/B3b) is worse on AMI MAE, B3b worst at 12.64. B4 does not
    dominate every axis either -- B3b beats B4 on pooled Humor and Intimacy
    rho, B3a beats B4 on Curiosity rho. **No single arm is best on
    everything**; a report claiming "B3b/B4 wins" must show axis and source
    detail, not only the pooled mean.

11. **Housekeeping gaps confirmed:** `flash_lite_axis_teacher.py` does not
    persist raw model output/generation settings/timestamps despite the
    module docstring's framing, and its resume logic keys only on
    utterance text -- a changed prompt would silently reuse stale scores on
    a resumed run. No evidence this happened here (single frozen prompt,
    verified complete 2,940/2,940 and 200/200 coverage with no duplicates),
    but the gap should close before this pipeline is reused.

## Corrected headline table (dev-200, post-L2-fix, mean Spearman rho / MAE)

| Arm | rho | MAE | Notes |
|---|---:|---:|---|
| B0 rule | 0.344 | 12.53 | best on Energy (0.505) and AMI MAE (11.76) |
| B1 kNN on existing weak labels (k15/bigram, sweep max) | 0.362 | 13.21 | selection-optimistic; unselected configs score 0.29-0.30 |
| B2 hybrid (B0+B1)/2 | 0.408 | 12.36 | |
| B3a ridge, same weak labels, different vocab (4k feature cap) | 0.428 | 12.67 | isolates label-vs-model only vs B3b, not vs B1 |
| B3b ridge, Flash-Lite-derived labels | 0.462 | 11.94 | pooled gain over B2 not clearly >0 at 95% (pre-fix bootstrap); Formality MAE 15.4-15.6, far worse than B2's 9.6 |
| B4 Flash-Lite called live | 0.542 | 11.00 | does not dominate every axis; per-turn API cost; parallelizability unmeasured, not proven blocked |

## What this cycle changes about the plan

- **No production decision follows from this experiment yet.** It is a
  development-stage finding on a repeatedly-analyzed dev set, with one
  known unresolved defect (B3b's Formality bias) and one corrected
  implementation bug (ridge L2).
- Before any report asks teammates to decide between B2/B3b/B4: fix or
  explicitly flag the Formality bias in B3b, rerun the bootstrap on
  post-fix predictions, add the shared-vocabulary B1-vs-B3a ablation Codex
  named, and show per-axis + per-source tables (not only pooled means).
- U1 (keep human-gold gate vs. change the goal) and the reserved-176
  evaluation plan are unaffected and still pending, per cycle 4b.

## Not doing

- Not opening the reserved final pool.
- Not changing `PALLY_AXIS_ANALYZER`.
- Not building the B3b deployment adapter yet (no candidate is frozen).
- Not applying a Formality bias correction calibrated on dev-200 itself
  (would be new dev leakage) without an explicit, separately-flagged plan.
