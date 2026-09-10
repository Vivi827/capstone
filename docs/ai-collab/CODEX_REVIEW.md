# CODEX_REVIEW — Round 2: adversarial methodological review

2026-09-10. **Recommendation: diagnosis first; reduce calibration to 30 items × two reviewers before the first40 human-value experiment. Hold 4×90, bulk labeling, and the E/H pilot.** Claude's main direction is sound, but the evidence does not identify a single teacher bottleneck and the proposed experimental order postpones a necessary measurement check too far.

Only this review file was changed. The reserved final-pool file and reservation audit were not opened, and no reserved predictions/labels were inspected. No labeling API was called. Numerical checks below ran in memory with `python -B` against existing non-reserved data. This document proposes development decisions; it does not amend the acceptance gate, authorize runtime changes, or manufacture human labels.

## 1. Findings supported by repository checks

### High: 100/200 dev rows share training groups; annotation conditions also differ

Using `scripts/reserve_ml_transition_final_pool.py::recover_nict_training_groups` and `training_group_set`, I recovered **600/600** NICT training rows, representing **470 groups**. Comparing their canonical provenance and the other training groups with `ml_transition_gold_human_200.jsonl` gives:

| Source | Training-overlapping dev rows | Non-overlapping dev rows |
|---|---:|---:|
| AMI | 65 | 2 |
| NICT | 28 | 40 |
| Taskmaster | 7 | 58 |
| Total | **100** | **100** |

Dev-200 contains 161 canonical groups. Casefold/whitespace-normalized exact training/dev text overlap is zero; this does not eliminate conversation-group leakage. `ai/evaluate_axis_analyzers.py`'s `gold-holdout` branch merely loads train and gold separately, without enforcing group exclusions. Its “frozen” description is stale for this repeatedly analyzed dev set.

The non-overlapping 100 are a sensitivity slice, not a new independent test, and contain only two AMI rows. Also rerun comparisons with a common training set purged of **all dev-200 canonical groups**, recovering NICT provenance before filtering. Freeze membership across comparison arms.

All **200 rows** of `ml_transition_gold_blind_review_200.csv` have nonempty previous/next-turn context. Current inference and new review batches show only the current utterance. Availability does not prove reviewers used context, but equal information conditions have not been established. Historical gold cannot simply be renamed current-utterance-only gold.

The reviewer/source confound is verified:

| Reviewer field | Source allocation | Humor ratings |
|---|---|---|
| `reviewer-avg` | AMI 67, NICT 33 | 76 zeros, 24 nonzeros |
| `reviewer-01` | Taskmaster 65, NICT 35 | **100/100 zero** |

NICT spans both regimes, so source and reviewer are not completely separated across the whole dataset. AMI and Taskmaster nevertheless remain confounded with reviewer regime. Pooled correlations cannot resolve teacher bias, annotation scale, and information mismatch. Report source × reviewer slices and NA correlations; shared rescoring is needed to resolve reviewer effects.

### High: Claude's 338 / 938 / 3,137 comparison does not identify teacher versus capacity

Verified experimental-set composition:

- 338 seed rows: 110 `gemini_assisted`, 99 `gpt_assisted`, 99 `claude_assisted`, 30 `ai_generated`.
- 600 NICT rows: `label_status=human_reviewed`, but `labeler=codex_accept_draft_per_user`.
- 2,199 `ai_draft_needs_human_review` rows: CHiME 600, AMI 599, HCRC 500, Taskmaster 500.

Thus the remaining 938 are not established independent human training labels. “Drop the AI drafts” obscures that provenance. Also, `draft_axes` is a deterministic lexical/bucket heuristic, not an LLM scoring call. A rubric-guided LLM is a different automation method, not simply more of the existing teacher.

Deleting 2,199 rows simultaneously changes source coverage, label distributions, corpus size, IDF, neighbor support, and density. `TfidfKnnAxisRegressor.fit()` learns IDF from supplied rows and prediction chooses top-k neighbors. Fixed IDF alone would not remove changed-neighbor confounding.

I ran the proposed comparison with **k=5, word_ngram_max=2**, matching the quoted baseline:

| Training | Dev-200 MAE | Dev-200 mean rho | Non-overlap 100 MAE | Non-overlap 100 mean rho |
|---|---:|---:|---:|---:|
| Full 3,137 | 14.897 | 0.2796 | 16.028 | 0.2876 |
| Seed 338 | 17.074 | 0.3184 | 17.348 | 0.3513 |
| Seed + accepted NICT 938 | 15.456 | 0.2940 | 16.630 | 0.2638 |

Deleting drafts improves pooled rank slightly but worsens MAE. The 938-row rank comparison reverses direction on the non-overlap slice. These exploratory point estimates have no confidence intervals. They do not support “teacher is the bottleneck, not data volume,” nor “more weak data makes it worse.”

For stronger discrimination, change labels on **the same training texts**, with membership, representation, IDF, and k fixed. Separately change representation/k with labels and texts fixed. Keep source-matched size curves as another experiment, not a causal substitute.

### High: calibration's claimed sampling method and probability guarantee are unsupported

`scripts/build_calibration_pilot_sets.py::_take_by_hash` sorts **rows** by a hash of group plus utterance, then takes the earliest row from each unseen group. This is not uniform group sampling followed by random within-group sampling, as the contract states. Larger groups have more chances to receive an early hash.

Actual eligible non-laughter pools after train-120 exclusion:

| Source | Rows | Groups | Rows/group |
|---|---:|---:|---|
| AMI | 159 | 39 | 1–8 |
| NICT | 322 | 242 | 1–7 |
| Taskmaster | 355 | 321 | 1–3 |

AMI laughter groups are explicitly excluded first. Accordingly, the calibration guarantee cannot cover all AMI candidates. The residual-arm shuffle is also ineffective because `_take_by_hash` immediately sorts its input again.

`1 - 0.9^30 = 95.76%` is correct for 30 independent opportunities with event probability 10%; it does not prove this algorithm offers that guarantee. “Any pair among four reviewers differs by >20” is a different event from “the fixed A/B pair differs by >20.” Four scorers do not create four independent item samples.

Before distribution, select unique groups directly with a fixed seed, then choose a random utterance per group. Define the eligible population and prevalence unit. Keep targeted rare cases separate from a probability-sampled calibration arm.

### Medium: teacher drift is verified, but its causal scope is narrower than claimed

I reproduced **132/600** generic-vs-stored bucket mismatches, **0/600** NICT-vs-stored mismatches, and **221/600** rows differing from current `draft_axes`. However, only Formality and Energy change: mean absolute differences **2.58 / 1.10**, maxima **7 / 3**. Intimacy, Humor, and Curiosity reproduce stored NICT values exactly.

This establishes generator/stored-label mismatch, not which version is more human-accurate or why every ML axis is weak. Claude's “that is what produced the current ML weakness” is premature.

Bucket sensitivity is important: direct-teacher Intimacy rho changes **0.09 → 0.29**, MAE **28.91 → 19.96**, with source-specific assignment. This is a direct-teacher comparison, not a measured trained-ML improvement. Do not count it as a student gain without controlled retraining.

### Medium: several proposed improvements are only checks, and configurations matter

- The quoted rule / ML / hybrid results reproduce as **14.535 / 14.897 / 14.262 MAE**, **0.3720 / 0.2796 / 0.3859 rho**, with full training and **bigrams**. Unigram full-training ML gives **15.310 / 0.2718**, its hybrid **14.581 / 0.3816**.
- `load_default_axis_dataset()` defaults to `data/axis_dataset_week2.jsonl`, which contains **338 rows**, unless explicitly configured. The runtime adapter defaults to unigrams. The pilot builder uses these implicit defaults; the train-120 selector explicitly uses experimental training and bigrams. The pilot manifest lacks training hash/k/ngram, so its historical selection model is not established by that manifest.
- The 3,137 rows contain **zero duplicate utterances** under casefold/whitespace normalization. Same-text dedup cannot explain this baseline's weakness. It matters later when merging reviewer rows: two scorers must not become two training neighbors.
- The gold CSV contains **175 fractional cells** truncated in JSONL. Using recovered CSV decimals with the same bigram predictions changes MAE **14.897 → 14.8905**, with unchanged rho **0.2796**. Correct the precision path, but this measured effect does not explain the gap.
- `_validate_partial_axes` still casts to `int`. `predict_partial` cannot recover lost target fractions. On full-label unigrams, unrounded predictions change MAE **15.310 → 15.3029**, rho **0.2718 → 0.2704**. Output precision and missing-axis supervision are distinct interventions.

## 2. Direct answers and recommended defaults

### (a) Diagnosis-first experiments in priority order

Keep dev-200 for diagnosis/selection only; never train on its labels. Freeze configurations, canonical exclusions, hashes, and fixed rule/old-hybrid comparators. The experimental training SHA-256 checked here is `23051000c3c2c4e0c38a876de61973d156188ef151faad69fca18caf20ddc1e9`.

1. **Measurement and leakage:** rerun original/decimal targets, explicit 338/3,137 and unigram/bigram configurations, source/reviewer slices, and common dev-group-purged training. Preserve historical results separately. The measured decimal effect is only 0.0065 MAE, so it gives no reason to expand labeling. A reversal after group purging would undermine the original label-volume rationale.
2. **Teacher fidelity versus representation:** create a group-held-out split within training data and measure student agreement with stored weak labels without same-group neighbors. Separately measure current-teacher/stored-label mismatch. On dev, compare teacher/student with the same text and bucket policy. With labels fixed, test k={3,5,9}, unigram/bigram, and one case/repeated-punctuation ablation if the actual transcript/STT inputs retain those features. Fit nothing on dev labels.
3. **Mixture/size curves:** retain the measured 338/938/full comparisons as mixture ablations. Add source-stratified group samples at 25/50/100% of weak data, five fixed seeds, and fixed-versus-refitted training-IDF sensitivity. Test HCRC exclusion separately for the transition-eligible recipe. Consistent gains from matched weak-data growth favor automated scale; simple source deletion cannot identify a bad teacher.
4. **Same-text alternative supervision:** run (b); if promising, relabel a fixed eligible training subset with the alternative and compare students using old versus new labels on exactly those texts. Keep IDF, features, and k fixed. Alternative scores on dev never enter training. Direct teacher improvement alone does not prove distillation succeeds.
5. **Input limitation audit:** inspect context availability, text signals, constant targets, and conflicting targets for identical text where available. Analyze source/reviewer/event metadata after prediction, never as hidden inference features. Laughter annotations are not Humor gold. This audit can locate information gaps, but cannot establish a text-only ceiling.

Concrete diagnostic patterns below are **proposed examples, not observed results or new acceptance gates**:

| Hypothesis | Supporting numerical pattern | Label-volume decision |
|---|---|---|
| Supervision bottleneck | Student matches held-out weak targets well, e.g. MAE ≤5 and rho ≥0.80, while both have human rho ≤0.30; changing only labels improves affected-axis dev rho ≥0.05 and MAE ≥1 | Improve automated supervision first; target human labels if alternatives fail |
| Model/representation bottleneck | Same-text teacher reaches human rho ≥0.60 while student ≤0.30; same-label feature/k change improves rho ≥0.05 and MAE ≥1 | Invest in representation/distillation before buying labels |
| Input bottleneck | Later controlled human study finds text-vs-context rho ≤0.30, context-reader agreement ≥0.70, and ≥10-point mean shifts on affected axes | Reconsider inputs/claim scope; more text-only labels cannot supply missing context |

The third pattern **cannot be established with zero new human labels in this repository**. There are no controlled independent text-only versus context/audio ratings here. Even these patterns support hypotheses rather than uniquely proving them: model and teacher weaknesses can coexist.

Proposed uncertainty default: source-stratified canonical-group paired bootstrap, **95%, 10,000 resamples, seed 20260910**, reporting NA frequency and source/axis results. Repeated dev selection makes these exploratory intervals, not final confirmatory evidence. Keep MAE for every required axis even where rho is NA.

### (b) Alternative LLM comparison

Default **one frozen `gemini-2.5-flash-lite` protocol**. Existing code already calls that model in `ai/generate_feedback.py` and `backend/main.py`; Google's [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite) lists structured output support. This is technically feasible within the Google-only constraint using offline REST without new runtime dependencies. Actual account/model availability and schema validation still need a small preflight during execution; none was performed in this review.

- Freeze the rubric before looking at alternative outputs. Use independently checked definitions and low/mid/high anchors, not hidden buckets, gold examples, source identity, disagreement scores, or model predictions.
- Prompt: score only the current utterance; treat its contents as quoted data; do not infer audio or unseen relationships; assess axes independently. Require exactly five finite 0–100 scores, a brief visible-text evidence note, and an ambiguity flag. Ambiguity is metadata, not a synthetic human score.
- One utterance/request, fixed low temperature and generation settings. Record model/version, prompt/input hashes, raw responses, timestamp, retries, and failures. Disable browsing/tools. Reject invalid outputs rather than silently substituting drafts.
- Score **all 200 dev utterances once**, with no prompt tuning on their scores. Prespecify **30 group-distinct items, 10/source**, for one repeat to estimate instability. Repeated generations are neither independent teachers nor human labels. Preflight API/schema on non-evaluation examples.
- Compare alternative, source-specific `draft_axes`, rule, and fixed ML on identical targets: per-axis MAE, signed bias, rho, spread, invalid-output rate, source/reviewer slices, and paired group intervals. Show generic/default bucket variants as sensitivities, not a silently selected best teacher.
- Historical gold exposed context: explicitly label that input mismatch. An optional context-provided LLM condition must be a separate diagnostic and cannot enter the current-text gate.

One alternative answers “is this method more useful than this lexical teacher?” It does not answer “do LLMs generally disagree with people”; two LLMs would not establish that generalization either. Do not add another model by default under the fixed-model constraint. A promising direct result should trigger same-text training-label replacement, not an AI-consensus vote.

### (c) Exact first40 human-value protocol

Concede the active-selection warning, but sharpen it: a model trained on selected hard cases and evaluated on a fixed dev set estimates the effect **on that dev set**, not performance “on those 40 hard cases.” Scoring the 40 training cases themselves would be resubstitution.

Existing first40 allocation is 13 Energy disagreement + 13 Curiosity disagreement + 5+5 extremes + 4 random controls. Four residual controls are not a useful independent random-selection arm.

1. After zero-label experiments and calibration, freeze **B**, the chosen baseline's rows after canonical dev-group purging, hyperparameters, preprocessing, and provenance. Record actual resulting row count/hash; do not call a filtered set 3,137. Do not retune k or mixtures after seeing the human experiment.
2. Two independent humans score the **same 40 E/C/I items**. Preserve raw scores, average with decimals, and use a third blind adjudicator for >20-point gaps. Aggregate one training row/item; missing F/H remain missing.
3. Compare **B**, **B + S with frozen automated E/C/I labels**, and **B + identical S with human E/C/I labels**, where S is the 40 texts. Use identical B+S-derived IDF/vectors, k, per-axis eligible-neighbor logic, and rounding for the two addition arms. The automated arm is a separately tagged experimental control, never a fill for missing human axes. Replace rather than duplicate any identical training text's evaluated-axis supervision.
4. Keep F/H predictions from B for this E/C/I experiment. Refitting shared IDF on partial-label texts otherwise changes even unreviewed F/H geometry. Use explicit per-axis handling or frozen F/H models to avoid this hidden treatment.
5. Evaluate on **dev-200**, with the common B purged of all its groups. Primary: E/C/I macro MAE/rho, all three axis deltas, source/reviewer slices, and paired group intervals. Show the original non-overlap-100 sensitivity and five-axis guardrails against fixed rule/old hybrid. Never evaluate training/calibration items as held-out gains.
6. Default: defer the extra random arm until a positive signal justifies testing selection policy. Then draw **20 new group-random eligible texts**, independently of model scores, excluding dev/calibration/pilot/first40 and reserved groups. Compare 20 prespecified active texts versus those 20 random texts with equal E/C/I annotation and automated controls. Comparing 40 active with 20 random confounds policy with budget.

**Proposed expansion trigger, not a replacement acceptance gate:** human versus same-text automated control reduces E/C/I macro MAE by **≥1.0** and raises macro rho **≥0.05**, with paired 95% intervals excluding no improvement in the corresponding directions; no evaluated axis worsens by >1 MAE or >0.03 rho. It should also improve over B itself and not be solely a source/reviewer artifact. If satisfied, annotate at most the **remaining 80**, then reassess the learning curve; do not authorize thousands.

Stop expanding this recipe if gains are <0.2 MAE and <0.01 rho **and intervals exclude the worthwhile effects above**. Wide intervals spanning worthwhile benefit and harm mean **inconclusive**, not “human labels never help.” If new human labels scarcely change predictions, inspect how often those 40 rows enter top-k neighborhoods. Low intervention strength in 3,137-row kNN is not evidence against human judgment generally.

### (d) Calibration now/later/smaller

Default **smaller, before first40**. Claude's “human-value probe, then decide calibration” conflicts with contract §7's calibration/rubric prerequisite. Conversely, an honest human eval does not logically require a separate four-person 90-item calibration. Duplicate scoring measures disagreement; calibration changes shared interpretation. Neither independently establishes truth, and shared bias can survive perfect agreement.

Use **30 items = 10/source × two scorers × five axes = 300 scores**, after fixing sampling and instructional anchors. Use the two intended primary evaluation scorers. Keep C/D available for blind adjudication; if they later become primary scorers, first qualify them on shared items.

For a fixed pair's >20-point disagreement event with 10% prevalence and independent draws, revised detection is **`1 - 0.9^10 = 65.13%` per source**, versus 95.76% at 30/source. Simultaneous detection across three independent sources at exactly that prevalence is approximately **27.63%**, not 95%. For finite uniform sampling without replacement, use the hypergeometric calculation and actual eligible population. Neither formula transfers unchanged to the existing row-hash sampler or laughter-excluded AMI as a whole.

This is a screen, not proof of equivalence. Inspect every >20 gap, per-axis signed/absolute differences, and notes. A source-axis mean signed gap >10 or repeated >20 gaps triggers discussion and fresh shared rescoring before first40. No observed gap does not prove agreement. Escalate toward 30/source if the project needs the 95%-per-source screen or persistent source-specific inconsistency warrants it. If the rubric changes, keep old items as calibration development; assess the revised rubric on fresh items rather than pool versions to claim success.

### (e) Minimum honest independent evaluation

Default for this existing pool: **all 176 reserved items × five axes × two distinct trained humans**, after model, rubric, input, comparators, exclusions, and analysis are frozen: **352 item-reviews / 1,760 scores**, plus third-person adjudication where needed. Retain individual ratings and report model agreement with each scorer as well as mean/adjudicated targets. Do not replace missing ratings with any teacher or consensus.

Use the declared **106 final-gate + 70 reproduction** allocation. These counts and the single reference-only AMI item are from contract §2, not a new inspection of the pool. Gate4 must remain a separate untouched group set. Complete all tuning before either set's scores are disclosed; do not tune between final-gate and reproduction. Four complete scorers are unnecessary by default.

The defensible claim is improved agreement with independent human judgments **for the specified input/rubric and sampled NICT/Taskmaster distribution**, conditional on the existing gate and uncertainty. These English, deliberately sampled corpora do not establish Korean/mobile-STT, natural-traffic, prosody, or AMI-wide performance. Sample size alone does not guarantee power or nonconstant Humor labels. Required-axis NA or wide intervals mean no demonstrated pass; obtain new independent evaluation data under a prospective plan, rather than relax the gate or invent signal.

The 176×2 plan is a practical minimum for using this entire fixed pool with measured disagreement, not a universal sample-size theorem. Reserving unscored rows does not itself supply independent human evaluation, and dev-200 cannot replace it.

## 3. Phase 2 artifacts: retain, defer, correct

- **Retain** stable IDs, slot-specific blind exports/manifests, raw/adjudicated separation, and closed reservations. I verified train-1200 versus gold-600 canonical-group intersection **0**. Calibration/pilot/first40 have 90/54/40 distinct groups. Slot A score cells are empty in all three batches. Group disjointness depends on provenance and does not establish natural-distribution validity or eliminate semantic duplicates.
- **Correct calibration sampling/probability language before distribution.** Smaller batches need coherent common-item manifests. Telling reviewers to stop after ten items in independently shuffled 90-item workbooks would select different subsets.
- **Check instructional anchoring.** `export_calibration_workbook.py` calls examples real hand-labelled seed examples. Of eight displayed examples, seven match seed training texts; six reproduce seed scores exactly (five `gemini_assisted`, one `claude_assisted`). Another matching seed text has different displayed scores; one has no experimental-set exact match. This does not prove humans never checked them, but metadata does not establish independent human anchors. Human-check examples before using them to train reviewers or prompt the alternative teacher. Keep instructional examples out of evaluation.
- **Do not call calibration a model-independent test.** Current experimental training overlaps 50/90 calibration groups, 29/54 pilot groups, and 19/40 first40 groups. This is acceptable for calibration/training, not held-out evaluation; it is not final-pool leakage.
- **Defer pilot54.** Its 13 laughter groups and nine non-laughter controls are candidates, not mandatory annotation. Laughter is neither humorous intent nor an E/H gold score. Reducing calibration frees groups, so the nine-control allocation is contingent, not an immutable scarcity fact. Meeting/source and event selection remain confounds.
- **Record selection-model provenance.** First40 and pilot builders have different model/data defaults. Do not reinterpret old disagreement scores as if generated by the newly chosen model. Any reselection must precede seeing labels and follow a prospective policy.
- **Fix decimal handling before training on means.** Aggregation preserves floats; both full and partial ML validation still truncate. Partial-label support is not a complete decimal-preserving training path.
- **Reconcile stale instructions in subsequent authorized execution.** Contract §11 still says “calibration 48” while §7/§12 say 90; workbook language mentions two reviewers while four files exist. None of those files was modified in this review.

## 4. Concrete next-two-week order

**Days 1–3:** freeze baseline/exclusion ledger; run group-clean measurement, teacher-fidelity, and small representation/mixture experiments. Preserve all tried variants. Do not spend the week on dedup/decimal hypotheses whose current effects are absent/tiny.

**Days 3–5:** correct and run 30×2 calibration, check instructional anchors, and freeze the current-text rubric. Run the one-protocol Flash-Lite comparison after rubric stability. If scoring remains inconsistent, pause first40 at this prerequisite rather than purchase noisy labels.

**Days 6–9:** execute bounded first40 with same-text automated control and neighbor-influence audit if prerequisites hold. Test alternative training supervision if direct teacher results warrant it. Keep E/H pilot and the optional random-policy arm deferred unless evidence specifically calls for them.

**Days 10–14:** decide stop / inconclusive / at most 80 further labels by the prespecified evidence rules. Only if a model is ready, freeze everything and hand off 176×2 independent evaluation. Otherwise keep the pool closed beyond two weeks; a calendar deadline is not evidence for opening it.

I agree with Claude on avoiding bulk-label presumptions, retaining independent human evaluation, rejecting AI consensus as gold, and requiring a user decision for an actual goal change. I reject the teacher-only causal conclusion and delaying all calibration until after first40. Reproducing a teacher may remain an auxiliary diagnostic without voiding the human acceptance gate; replacing that gate is a separate decision this review does not make.
