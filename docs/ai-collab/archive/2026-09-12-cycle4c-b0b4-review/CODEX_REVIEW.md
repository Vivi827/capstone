# CODEX_REVIEW — cycle 4c, Round 2

Reviewed 2026-09-12. **All six headline numbers reproduce, but the ridge implementation, causal interpretation, and latency justification need correction before sharing the report.** B3b is a promising development candidate; these results do not establish production readiness.

Scope: repository code, existing training/dev data, read-only Git history, and in-memory computations. No external API calls; the reserved final test pool was not opened. Only this file was written. HEAD was `ededb01` initially and changed externally to `675fd4d` during review; that commit adds review setup and four tests without changing the evaluated model/scripts/data. I did not commit, push, reset, pull, or switch branches.

## 1. Reproduction and leakage audit

Re-ran `python -B scripts/experiment_b1plus_linear_student.py`, then captured the same predictions in memory for additional checks. All 200 rows have all five gold axes; overall rho uses five axes for every arm.

| Arm | Recomputed mean rho | Recomputed MAE |
|---|---:|---:|
| B0 rule | 0.344165 | 12.528 |
| B1 kNN, k15/bigram | 0.362421 | 13.207 |
| B2 rounded 50/50 hybrid | 0.408131 | 12.361 |
| B3a current linear implementation, weak labels | 0.438773 | 12.590 |
| B3b current linear implementation, Flash-Lite labels | 0.480327 | 11.887 |
| B4 cached Flash-Lite dev scores | 0.542188 | 10.995 |
| Additional existing arm: kNN, Flash-Lite labels | 0.390558 | 12.359 |

The last arm already exists in the experiment and should accompany the comparison: teacher replacement also helps kNN, but does not bring its rho above B2. B4 here is a cached-score evaluation, not a new measurement of live service behavior.

Leakage checks passed for the specified boundary:

- Recovered **600/600** original NICT training rows using `source_line` with matching raw text. Reconstructed the purge: **3,137 → 2,940** rows.
- The actual saved `ml_transition_train_purged_2940.jsonl` contains exactly the reconstructed texts in the same order, and every saved field agrees. It omits provenance fields, so provenance must be checked by joining back to original rows, not by trusting its own fallback group keys.
- Recovered canonical groups of reconstructed training rows have **zero intersection** with dev groups.
- Saved training texts and Flash-Lite training-score texts each have **zero exact overlap** with dev texts. Also zero after casefolding and replacing runs of non-word characters with spaces.
- Flash-Lite training-score texts exactly equal the 2,940 purged texts; no duplicates or missing labels. Dev scores contain 200 unique texts and cover all dev rows. B3a/B3b really use the same texts here.

This rules out the checked group/text contamination, not all semantic near-duplicates or foundation-model pretraining exposure. The teacher request contains only the utterance and fixed system prompt, with no dev-gold field. There is no observed B4-to-human-gold write path; repository inspection alone cannot certify the entire human annotation process.

Reproducibility hashes (SHA-256):

```text
ml_transition_gold_human_200.jsonl
998fce0f2c8c0b4009b469d2a385b0f78a37890b648672687d6997ffe3c65a6c
ml_transition_train_purged_2940.jsonl
d48135514291028c7c80035fe3a50a19afd76ccf580ae05a98a8d4669bcff49f
flash_lite_train_purged_scores.jsonl
27c4c4fbc7730d2474db4b2da80457a5756ea625475ca2e762a237bcf33eebfb
flash_lite_dev200_scores.jsonl
f1e9956a15252508b331ffb52595d005dc0c694ce31cc784b43a72dcf6d47731
```

## 2. High: the update is not ordinary isotropic ridge regression

`ai/linear_axis_model.py:122–125` uses, for a batch of size m:

```text
scale = lr / m
w[j] -= scale * (sum_i error_i*x_ij + l2*w[j]/m)
```

The squared-error gradient and unpenalized intercept update are sensible. But shrinkage is **lr*l2*w[j]/m²**, applied **only to coordinates present in the batch**. Ordinary ridge for mean half-squared error plus `lambda/2 * ||w||²` applies `lr*lambda*w[j]` to every coordinate, including absent features. Even choosing another global normalization cannot explain absent-coordinate exemption: effective regularization depends on feature frequency and batch composition. At batch size 32 the shrinkage factor uses 1/1024; the final 28-row batch uses 1/784.

This is a learned sparse linear predictor with an unusual batch-dependent penalty, not evidence about a correctly implemented standard ridge solution. Its plausible score does not validate the mathematics. Correct the objective/update, check a tiny analytically solvable case and absent-feature shrinkage, then regenerate B3 results before calling them ridge results. Alternatively describe the current algorithm accurately and avoid ridge-specific conclusions.

Convergence is unestablished. With B3b defaults, normalized-label training MSE was **0.008463 at 40 epochs**, versus **0.006203 at 80** (about 27% lower). Dev rho/MAE changed from **0.480327/11.887** to **0.487528/11.824**. This is a diagnostic sensitivity check, **not a recommendation to select 80 epochs on dev**; training loss and the intended regularized objective need a convergence criterion.

Correction to self-audit item 5: at final review state, `tests/test_linear_axis_model.py` exists and `python -B -m pytest -q -p no:cacheprovider tests/test_linear_axis_model.py` passes **4 tests**. They cover signal recovery, bounds, partial-label output shape, and seeded repeatability. None verifies the L2 gradient or convergence; the mathematical concern survives those passes.

## 3. High: B1 → B3a does not isolate model family alone

`RidgeAxisRegressor._fit_vocab()` filters `min_df=2` and caps vocabulary at **4,000**. kNN retains **17,913** bigram/unigram features on the same training set. Ridge discards out-of-vocabulary features; kNN vectorization retains them with default IDF 1.0. Both use related TF-IDF/tokenization, but do **not** have identical effective features.

B3a versus B1 changes estimator, vocabulary filtering, and optimization/regularization together. It supports “this linear pipeline outperforms this kNN pipeline on dev,” not an isolated capacity effect. Global linear regression is not categorically a capacity increase over instance-based kNN. A shared-vocabulary/vectorization comparison is the missing ablation.

B3a → B3b **does** isolate label replacement within the current linear implementation: same text order, vocabulary, defaults, and seed. That is useful, subject to the model bug and uncertainty. B3b versus B3a is a teacher-label intervention, not a capacity increase.

## 4. High: the claimed reply-generation dependency is absent

`backend/main.py:844–855` computes axes/character before calling the reply function, but `_call_gemini_chat()` at line 694 accepts only utterance, history, character **name**, and level. Its prompt is built from name and level; computed axes, character parameters, and `describe_character()` labels are not passed. The later audio-turn path at lines 1475–1482 has the same property.

Thus “axis result feeds the reply-generation prompt, so it cannot fully parallelize” is false for this repository state. The current code executes sequentially, but there is no demonstrated data dependency preventing concurrent axis scoring and reply generation. An asynchronous implementation and latency measurement are still needed; parallelization is not already implemented or proven cost-free.

B3b's `predict()` performs local TF-IDF/vector dot products and requires **zero external scoring API calls**. Its import chain adds no NumPy/SciPy/sklearn dependency. However:

- It still performs local model inference: label the column “external axis-scoring calls per turn,” not “inference calls.” Other application API calls remain.
- There is **no deployed B3b adapter** in this repository. `ai/analyzers.py:74–82` supports only rule/ml/hybrid; `ml` selects kNN. There is no ridge serialization/loading path here. “Ships as-is” and “B3b's deployed form” overstate implementation status.
- B4's scoring utility can retry requests up to three times. “1” is the intended successful scoring request, not a verified upper bound on attempted calls or latency.

## 5. Selection, history, and statistical strength

Recomputed all **15** k/ngram cells. k15/bigram is the maximum, rho **0.362421**. Defaults k5/unigram give **0.296534**; k5/bigram gives **0.288376**. Apparent gains are **+0.065887** and **+0.074044** respectively. These differences are **not estimates of selection optimism**: they combine genuine configuration improvement with selection noise. The amount of optimism is not identifiable from this sweep alone. Nested group-held-out selection/evaluation or a frozen independent evaluation is needed to estimate it; assigning a numerical bias without that would be invented precision.

The bigram choice transfers dev-informed selection into B3a/B3b and B2. Ridge itself has no k parameter. Git history shows one introduction of ridge defaults in `5466e39`, alongside reported dev results; I found no recorded sweep of l2/lr/epochs/batch_size/min_df/max_features. This is consistent with “picked once,” but **does not independently establish an a-priori choice**: no pre-result registration exists in the inspected history. I cannot verify the author's unseen decision process. B0 has no tuning in this sweep and B4 has a fixed current prompt; that does not make their dev scores independent acceptance estimates.

**The claimed full ranking across two “independent” dev states is contradicted by history.** Commit `255a332` and diagnosis-log §11 record pre-re-review best kNN **0.350 < rule 0.372**. The current order reverses that pair. These are also the same texts with revised labels, not independent replications. Ridge first appears after re-review commit `4f809db`; its initial commit supplies no full pre-re-review B0–B4 replication.

I found bootstrap **requirements/proposals**, not existing numerical B0–B4 intervals, in relevant scripts/history and `docs/ml-transition-contract.md:169–175`. I ran this exploratory bootstrap in memory:

- Fixed reproduced predictions; no retraining or reselection.
- Group key: `canonical_group(gold_row)`. Dev has **161 groups**: AMI 39, NICT 61, Taskmaster 61, with 67/68/65 rows respectively.
- `random.Random(20260912)`, 1,000 replicates. For each source in sorted order, sample its original number of groups with replacement, append all rows in selected groups, and reuse identical indices for every arm. Group insertion order follows gold file order.
- Recompute tied-rank Spearman per axis and its NA-aware mean. Sort paired rho differences; use elements 24 and 974 as approximate percentile endpoints. No overall replicate lost an axis for these three arms.

| Paired mean-rho difference | Observed | Exploratory 95% percentile interval |
|---|---:|---:|
| B3b − B2 | +0.072196 | [+0.001075, +0.148523] |
| B4 − B3b | +0.061861 | [+0.012300, +0.114843] |

These give some conditional evidence of improvement; “there is no bootstrap evidence” would now be wrong. B3b−B2's lower endpoint is especially close to zero. These post-hoc intervals do **not** account for repeated dev analysis, configuration selection, nonblind relabeling, rubric uncertainty, or production generalization. They are not multiplicity-adjusted final-gate intervals, and 1,000 resamples create no new independent data. The ranking remains a development finding, not a confirmed production result.

NA drops axes, not rows: Taskmaster has 65 rows and four defined rho axes, not fewer rows because Humor was omitted. Overall all five axes are defined. Source means do not all average the same axis set.

## 6. Important regressions hidden by the headline mean

| Diagnostic | B0 | B2 | B3a | B3b | B4 |
|---|---:|---:|---:|---:|---:|
| Formality MAE | 11.945 | 9.620 | 8.740 | **15.405** | 14.930 |
| Energy rho | 0.505 | 0.426 | 0.338 | **0.389** | 0.698 |
| Intimacy MAE | 11.295 | 14.050 | 17.305 | **14.620** | 13.135 |
| Curiosity rho | 0.759 | 0.774 | 0.793 | 0.771 | **0.742** |
| AMI mean MAE | 11.76 | 12.27 | 12.39 | **12.64** | 10.54 |
| NICT mean rho | 0.255 | 0.358 | **0.478** | 0.405 | 0.440 |

B3b's Formality MAE is **+5.785 worse than B2**, while overall MAE improves by only 0.474. Energy rho loses about 0.037 to B2 and 0.116 to rule. Flash-Lite label replacement lowers NICT rho versus B3a despite raising the pooled mean. B4 also fails to dominate every axis. Calling it a “teacher ceiling” is misleading: B3b exceeds B4 on overall Humor and Intimacy rho, and B3a exceeds B4 on Curiosity rho.

Reviewer/source confounding is measurable beyond the acknowledged nonblind re-review. reviewer-avg contains AMI 67 + NICT 33; reviewer-01 contains NICT 35 + Taskmaster 65. B3b−B2 mean-rho gain is **+0.0933** on reviewer-avg and **+0.2309** on reviewer-01. The gain is not confined to revised labels, but reviewer-slice differences cannot be attributed to reviewer behavior alone. Pooled rho includes between-source/rubric differences; it is not the average within-source rho or a production-distribution estimate.

The existing STT ablation evaluates rule/kNN/hybrid. I additionally replayed B3b with `diagnose_stt_input_skew.strip_punct_lower()` applied to dev input, retaining original training and gold: mean rho **0.475802**, MAE **12.219**; Curiosity rho fell **0.771368 → 0.640885**, MAE rose **13.405 → 16.015**. This deterministic stress test is not actual STT accuracy. B4 on transformed inputs remains unmeasured; cached original-text scores cannot establish behavior on altered text.

## 7. Required corrections and missing experiments

1. Correct the ridge objective and validate update/convergence before freezing a candidate; rerun paired comparisons afterward. Keep this review's 80-epoch probe explicitly exploratory.
2. Add the shared-feature comparison before claiming isolated model capacity. Preserve the same-text teacher comparison and existing kNN/Flash-Lite arm.
3. Report per-axis MAE/rho, source slices, group counts, and conditional uncertainty. Predefine acceptable regressions; a positive mean-rho interval does not satisfy every gate.
4. Evaluate candidates under the agreed serving-input transformation, including B4 when API experiments are separately authorized, and measure end-to-end timing after an adapter exists.
5. Preserve a teacher run manifest: model/version, prompt hash, generation settings, input hash, time, and request/retry outcomes. `flash_lite_axis_teacher.py:155` stores only text/source/axes/evidence despite its docstring promising raw output. Resume keys only on utterance, so a changed prompt could silently reuse old scores. I found no evidence of mixed prompts, but current files cannot independently prove frozen-generation history. The experiment also accepts partial teacher coverage once 200 rows exist (`experiment_b1plus_linear_student.py:164–169`); future paired runs should fail unless intended coverage/text equality holds. This run has complete coverage.
6. Finish the source report before circulation: CONTEXT points to diagnosis-log §12 for B3/B4, but the inspected log ends at §11. Replace “decisively ahead,” “independent states,” “same feature pipeline,” and the asserted serial dependency with the qualified findings above. Freeze the existing acceptance protocol before opening reserved data.

Recommended report conclusion: **“All reported dev scores reproduce with verified group/text exclusion. The Flash-Lite-labeled local linear candidate improves pooled dev metrics, with substantial axis-specific tradeoffs. Its regularization implementation requires correction and independent validation before a runtime transition decision.”**
