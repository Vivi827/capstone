# Codex Round 2 — cycle 4d methodological review

Reviewed HEAD `108f6b8e623658a4b47c2c3da24cb12dfe66feff`. No external API calls; the reserved final pool and its row-level audit/reservoir were not opened. Computations ran in memory with `python -B`. This review is the only file written. `docs/ai-collab/runs.log` was already modified on entry and was left alone.

**Verdict:** the matched-vocabulary score and all three post-fix bootstrap intervals reproduce. They support continued experimentation, not a B3b deployment decision. The most consequential new finding is that the alleged 208 human-edited NICT labels are unsupported by the saved data. They cannot supply independent calibration truth. The report also retains stale comparisons and understates B3b's post-fix Energy regression.

## 1. Matched-vocabulary ablation: reproduced, with narrower interpretation

Using the paths and provenance recovery in `scripts/bootstrap_b0_b4_comparison.py`:

- All 600 NICT training rows recover to raw provenance successfully. Purge leaves **2,940 training rows**, including 567 NICT rows.
- No stripped/case-folded exact utterance overlap remains between purged training and dev-200. This does not establish near-duplicate or speaker disjointness.
- Flash-Lite training scores contain 2,940 distinct utterances; dev scores contain 200 distinct utterances. Prediction reconstruction succeeds without missing score lookups.
- Dev SHA-256 is `998fce0f2c8c0b4009b469d2a385b0f78a37890b648672687d6997ffe3c65a6c`.

| Configuration | Vocabulary | Dev mean rho | Dev mean MAE |
|---|---:|---:|---:|
| kNN, k=15, bigram | 17,913 | 0.3624207440 | 13.207 |
| Ridge, bigram, min_df=1, max_features=999999 | 17,913 | 0.4201768051 | 13.073 |
| Ridge, bigram, default min_df=2/max_features=4000 | 4,000 | 0.4278617950 | 12.672 |

Matched ridge gains **+0.057756 rho**, but only **−0.134 MAE**, over this kNN configuration. It does not dominate every axis: Humor rho is **0.07482**, below kNN's **0.11862**, and Formality/Curiosity MAE worsen.

### Feature audit

`ai/linear_axis_model.py::_fit_vocab/_vectorize` and `ai/ml_baseline.py::fit/_vectorize/_cosine` share tokenization, TF scaling and training IDF. I compared complete IDF dictionaries: **exactly equal**. After mapping ridge indices back to tokens and normalizing kNN training vectors, the maximum feature-value difference over all 2,940 rows is **0**. Feature index ordering is not an additional representation confound here.

There is a prediction-time difference: ridge drops unseen tokens; kNN retains them with IDF=1 in its query norm. **191/200** dev queries contain unseen features. However, these features multiply every positive cosine for a query by the same factor, which cancels in its normalized neighbor-weighted prediction when selected similarities are positive. Actual checks: **zero** queries have a zero-similarity 15th neighbor, and filtering unseen query tokens changes **0/200** rounded kNN predictions. Do not claim an observed OOV performance confound merely because the implementations differ.

One dev query has a similarity tie at the k=15 cutoff. kNN sorts `(similarity, training_index)` descending, so tie selection depends on training row order. I did not quantify that tie's effect. This is an implementation sensitivity, not evidence that the improvement is false.

The L2 repair now shrinks every weight each step with the expected full-data scaling. Nevertheless, ridge uses fixed-step SGD (40 epochs, constant learning rate, one seed), without a convergence certificate. The supported statement is: **this SGD-trained ridge configuration outscored this kNN configuration with matched training features**. It does not establish general estimator-family superiority or statistical significance. A training-only convergence/seed sensitivity check, comparable tuning budgets, and a paired interval for the matched comparison would strengthen that claim. Do not select the best new seed/epoch on dev and call it independent verification.

The ablation is not exposed by the experiment CLI; its default still fits 4,000 ridge features. Reproduction in memory after `import scripts.bootstrap_b0_b4_comparison as b`:

```python
tr = b.load_jsonl(b.TRAIN_PATH)
raw = b.load_jsonl(b.NICT_RAW_PATH)
gold = b.load_jsonl(b.GOLD_PATH)
dev_groups = {b.canonical_group(x) for x in gold}
purged = [x for x in tr if b._row_group(x, raw) not in dev_groups]
examples = [b.LinearAxisExample(x['utterance'],
    {a: float(x['axes'][a]) for a in b.AXIS_KEYS}, x['source'])
    for x in purged]
model = b.RidgeAxisRegressor(word_ngram_max=2, min_df=1,
    max_features=999999).fit(examples)
print(len(model.vocab), b.mean_rho(gold,
    [model.predict(x['utterance']) for x in gold], list(range(len(gold)))))
```

## 2. Bootstrap: reproduced, appropriate conditionally, not confirmatory

`python -B scripts/bootstrap_b0_b4_comparison.py` reproduces:

| Paired mean-rho difference | Observed | Percentile 95% interval |
|---|---:|---:|
| B3a − B2 | +0.0197 | [−0.0211, +0.0684] |
| B3b − B2 | +0.0542 | [−0.0162, +0.1320] |
| B4 − B3b | +0.0799 | [+0.0299, +0.1341] |

Whole canonical groups are sampled with replacement within each source; all arms reuse the same indices. Ranks are recomputed after resampling, including duplicates and ties. This is appropriate for a paired, fixed-model, source-stratified cluster bootstrap **assuming canonical groups are the independent units**.

| Source | Rows | Groups | Group-size counts |
|---|---:|---:|---|
| AMI | 67 | 39 | 11 singletons, 28 pairs |
| NICT | 68 | 61 | 54 singletons, 7 pairs |
| Taskmaster | 65 | 61 | 57 singletons, 4 pairs |

AMI's 39 groups are a limitation, not automatic invalidation. Keeping pairs together respects within-group dependence. Independent row resampling would usually understate positive within-group dependence. However, this code establishes meeting/interview/dialogue grouping, not independence across recurring speakers or other higher-level relationships. A stronger grouping, if warranted by provenance, would ordinarily reduce effective sample size and may widen intervals. That higher-level audit remains unperformed.

Remaining qualifications:

1. **Fixed group counts do not fix source row proportions.** With unequal group sizes, source row counts/weights fluctuate across replicates. This is coherent for a cluster-resampling estimand, but not exactly a fixed 67/68/65 mixture. For a fixed source-mixture estimand, define fixed source weights and a corresponding weighted-rank statistic. Averaging per-source correlations is another estimand; report it separately. Neither change has a guaranteed effect on interval width.
2. **Pooled rho is not within-source performance.** Source differences can contribute to rank agreement. Source strata do not remove reviewer/source confounding: all 67 AMI rows are reviewer-avg, all 65 Taskmaster rows reviewer-01; NICT splits 33/35. NICT allows a descriptive within-source reviewer comparison, but different texts still preclude identifying a reviewer effect.
3. **NA bookkeeping is incomplete.** `mean_rho()` drops undefined axes separately by arm. All observed overall arms have 5/5 valid axes, but the bootstrap does not report per-resample undefined-axis frequencies or enforce a common axis set. It therefore cannot certify that every difference uses the same metric. I did not instrument those frequencies; this is a reporting/robustness gap, not a demonstrated explanation for the intervals. Contract §8 explicitly requests that bookkeeping.
4. **Intervals condition on selected configurations, fitted weights and fixed cached teacher scores.** They omit training/seed variation, teacher-call variation, the 15-cell selection, earlier dev analyses and rubric/reviewer uncertainty. B2 inherits selected kNN settings too. Pairing does not remove selection optimism. A zero-crossing interval means improvement remains unresolved under this procedure, not equivalence or proof of no benefit.
5. **The positive B4 interval establishes only the tested B4−B3b exploratory mean-rho contrast.** “Only live Flash-Lite is confidently better than what came before it” generalizes beyond the tested comparisons, metrics and population. The script provides three unadjusted exploratory intervals, not all-model, all-axis or production superiority.

For a frozen report, use at least 10,000 paired group replicates, input hashes/model settings, NA frequencies/common-valid-axis sensitivity, and source/axis MAE and rho contrasts. More replicates reduce Monte Carlo error; they need not widen or narrow the CI. A cluster-jackknife/BCa sensitivity could investigate skewness/influential groups, but its direction is likewise unknown. Including training/selection uncertainty would generally add uncertainty; its size must be measured. No bootstrap variant restores a fresh test after repeated dev use.

## 3. High-priority provenance error: the NICT labels are not a human calibration anchor

Diagnosis log §12 says “567행 중 208행만 사람이 Formality/Energy를 수정.” Saved data contradict that attribution:

- Join `nict_jle_labeled_human_600.jsonl` to `nict_jle_labeled_draft_600.jsonl` by utterance: **600/600 complete axis dictionaries are identical**.
- All 600 “human” rows have `labeler=codex_accept_draft_per_user`.
- The purged NICT subset matches the accepted-label file on **567/567** rows and differs from the saved draft on **0** Formality/Energy rows.
- `scripts/build_human_reviewed_nict_dataset.py` defaults to that accepted-draft labeler. Its `human_reviewed` status is not evidence of independent scoring.

The 208 previously observed discrepancies compare **current `draft_axes()` output against historical stored labels**, not saved draft against saved human scores. Their historical cause cannot be inferred as human editing. Archived `2026-09-10-execution-planning/CODEX_REVIEW.md` already distinguished these facts. Correct §12, §2's related attribution, and `scripts/diagnose_teacher_fidelity.py`'s “per-user ... edit” description before reusing this claim.

A concrete misleading correction: Flash-Lite minus the 567 stored NICT Formality labels averages **+12.2152**. Subtracting it calibrates toward accepted heuristic labels, not independently verified human scores. It is also NICT-only.

I checked train-review-1200 and active-EC-120: both are pending with **zero** filled Formality scores. Calibration slots A/B/C/D each contain 90 pending rows and **zero** filled Formality scores. No completed independent Formality anchor was established in these checked artifacts. A filename containing “human” is insufficient.

## 4. Formality strategy: retain the baseline; keep final data out of tuning

Post-fix B3b Formality MAE is **15.605**, versus B2 **9.620**; signed error is **+15.305** overall. This supports over-scoring, but not the claim that a single identical teacher offset is copied verbatim:

| Source | B3b Formality bias | B4 Formality bias | B3b Formality MAE |
|---|---:|---:|---:|
| AMI | +17.179 | +16.627 | 17.388 |
| NICT | +18.632 | +13.059 | 18.632 |
| Taskmaster | +9.892 | +10.800 | 10.600 |

A single scalar correction is not established as adequate. Teacher bias, student approximation and target-rubric uncertainty all contribute. A constant subtraction preserves unrounded/unclipped ranks; clipping/rounding can create ties. A Formality intercept fix cannot repair Energy regression.

**Recommendation:** keep uncorrected B3b as an exploratory reference, hold production work, and either explicitly retain the calibration limitation or authorize a small independent Formality-only study.

- **(a) Leave uncorrected:** reasonable now. “Decide later with reserved-176” must mean acceptance/rejection of one frozen candidate. Selecting corrected versus uncorrected models, estimating an offset or changing the rubric after viewing final results consumes the pool as dev under contract §§9–11. Do not convert the final-gate/reproduction split into calibration/reporting slices.
- **(b) Use already scored training texts:** possible only with an independent target anchor. Accepted NICT drafts and rule/hybrid outputs are not human truth. Distilling a rule or using mixed teachers is a possible new surrogate objective, but must be described and independently validated as such. The NICT offset above is not a warranted human-scale correction.
- **(c) Split dev-200 now:** acceptable as explicitly exploratory fitting, not a clean retrospective holdout. Both slices have informed diagnosis/model choice/rereview. Split by group, acknowledge smaller reporting samples and lost precision. Cross-fitting reduces direct within-fold calibration fitting but cannot undo previous adaptation to these labels.
- **(d) Preferred evidence if labeling is approved:** choose a small source-balanced set of nonreserved, non-dev groups from the already teacher-scored training domain. Blind-score Formality under a frozen input/rubric, with some independent same-text overlap to assess agreement. Withhold those groups from student fitting while choosing correction form/checking generalization. Human scores used to fit the correction are calibration data, not evidence that it succeeds. Keep the final acceptance protocol frozen. Budget, tolerable error and sample size need an explicit decision; an arbitrary small sample is not automatically sufficient.

This concentrates human effort on the deficient axis. If calibration remains paused, documenting the defect and holding the candidate is more defensible than claiming another teacher supplies independent truth.

## 5. B3b deployment adapter: hold

Recommend **hold B3b-specific production work**, but not because a zero-crossing interval proves ridge unsuitable. The contract does not universally require significant superiority in average rho: it includes MAE noninferiority, relative correlation, per-axis limits and independent reproduction. “Neither clears 95% superiority” alone is too crude a deployment rule.

There is a concrete unresolved gate issue: post-fix **Energy rho B3b=0.343945 versus B2=0.425700**, a difference of **−0.081756**, larger than the contract's 0.03 per-axis regression margin at the point estimate. Rule is **0.505004**. This is not a formal final-test failure, but warrants a targeted explanation/experiment before candidate-specific deployment work. Formality correction alone will not fix it.

Before resuming production-oriented adapter work: freeze comparator/candidate, settle Formality treatment, quantify Energy and other axis regressions plus MAE tradeoffs, and specify uncertainty-based gate decisions. Before runtime replacement: complete the independent gate/reproduction protocol and its required user approval. An inactive reusable serialization/interface prototype can separately be justified for engineering measurement without claiming statistical superiority. No implementation was performed here.

## 6. Corrections and missing experiments before team reporting

1. **§12 mixes pre/post-fix evidence.** Item 7 says the bootstrap is uncommitted and awaits rerun; the headline B3b note still invokes the pre-fix near-zero lower bound. Replace them with the reproduced intervals. Item 10's Energy rho **0.389** is stale (now **0.343945**), and B3b AMI MAE **12.64** is stale (now **12.474627**). Its claim that B3b beats B4 on Intimacy rho is false post-fix: **0.336723 < 0.358992**. B3b still beats B4 on Humor (0.235585 > 0.201230). Recompute item 9's reviewer-subgroup deltas instead of assuming they survived; I did not independently recompute those two deltas.
2. **§11 overstates rereview conclusions.** Rule rho fell after rereview, but MAE improved (14.54→12.53); “rule을 절대적으로 낮췄다” is metric-dependent. A nonblind rereview's ranking cannot strengthen independent generalization evidence. Sparse Humor under this rubric is observed; true rarity versus reviewer threshold remains unresolved without independent same-text review. Narrow “결정적으로 앞선다” to the specified exploratory mean-rho result.
3. **Nested selection remains unverified.** CONTEXT/CLAUDE_REVIEW still mark it pending; I found no committed nested-selection script/result. Require split seed/group counts, inner labels/objective, train-only vocabulary/IDF fitting, deterministic tie handling and refitting on all purged rows. Selecting against weak inner labels tests teacher fidelity, not necessarily human utility. One inner holdout followed by another look at this reused dev is a sensitivity analysis, not nested CV or an unbiased estimate of original winner optimism. Preserve the existing B2 comparator if selected k changes.
4. **Add contrasts that match the question.** Matched-ridge−kNN addresses estimator comparison; B3b−B3a addresses label replacement; source/axis MAE and rho address hidden tradeoffs. Three pooled intervals cannot answer all of them. B3a/B3b do match implementation/texts here, but targets change across all sources, including **338 seed/AI-assisted rows**. This is one particular supervision replacement, not universally “better labels.”
5. **Future-run validation is weak.** Scripts reconstruct predictions from mutable files without asserting hashes/provenance. The experiment permits a partial Flash-Lite subset once ≥200 rows are available; the bootstrap requires all lookups. Future runs could compare different training sets. Add expected coverage, duplicate/range/finite-value validation, hashes and exact model settings when scripts are revised. Current caches had full coverage and unique utterances; this is a future-run hazard, not a demonstrated current mismatch.
6. **Terminology:** §12 is ridge regression, not logistic regression. B0/B1/B2/B3a/B3b/B4 are six concrete arms. Flash-Lite direct is a teacher baseline, not a mathematical ceiling: students may denoise or outperform it on particular targets, as Humor already illustrates.

The defensible conclusion is that matched-feature ridge improves this kNN configuration's dev mean rho; improvement over hybrid remains unresolved for the current ridge candidates under the exploratory interval; B3b has material axis/calibration defects; final acceptance is untested. None of this authorizes opening the reserved pool for further model selection.
