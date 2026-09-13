# ML Transition Plan

> **STATUS 2026-09-10** — 이 문서 이후 두 번의 dual-AI 검토 사이클과 gold-200 사람
> 검수가 진행됐다. 아래 내용 중 낡은 부분이 있다:
> - **gold-200은 이제 "frozen acceptance test"가 아니라 "dev / diagnosis set"이다.**
>   반복 진단에 이미 사용됨. 최종 판정은 `data/fixtures/ml_transition_reserved_final_test_pool.jsonl`
>   (176행 / 156그룹, `final_gate` + `gate4_reproduction`)로만.
> - **AMI는 최종 test 범위 밖**으로 명시됨 (현재 pool에 엄격 그룹 1개뿐). 후속 확보.
> - 라벨 정밀도 · 검수 절차 · 평가 규약 · NA 정책 · gate #4 재현은
>   **`docs/ml-transition-contract.md`가 authoritative.** 충돌 시 contract 우선.
> - 진행 근거: `docs/ai-collab/DECISION.md` (실행 계획) 및
>   `docs/ai-collab/archive/2026-09-07-*/`, `docs/ai-collab/archive/2026-09-08-*/`.

## Goal

Make Pally's five-axis analyzer a single ML model. Hybrid remains a temporary
fallback, not the desired destination.

## Current Evidence

The experimental set has 3,137 rows: 338 seed rows, 600 NICT accepted-draft
rows, and 2,200 AI-draft rows sampled from CHiME-6, HCRC Map Task, Taskmaster-1
WoZ, and AMI meetings. Its labels are useful for model iteration but are not
independent human gold labels.

The word 1-2 gram TF-IDF k-NN model is the best ML candidate so far:

| Evaluation | ML MAE | Hybrid MAE | ML Spearman | Hybrid Spearman |
|---|---:|---:|---:|---:|
| Leave-one-out | **7.55** | 7.95 | 0.44 | **0.45** |
| Source-group holdout | **7.62** | 7.86 | 0.45 | 0.45 |

ML now wins absolute error in both tests, but it has not independently beaten
hybrid on rank separation. Do not make `PALLY_AXIS_ANALYZER=ml` the default yet.

## Research Alignment

The five axes measure a user's communication state. They are not a personality
trait model and they do not, by themselves, prescribe Pally's response style.
User-agent similarity, complementarity, and adaptation strength remain a
separate experimental policy question. The implementation plan for baseline
versus current state, conversation context, and policy experiments is in
`docs/communication-style-adaptation-plan.md`.

## Required Data

1. Keep the 600 gold and 1,200 train rows as **unlabeled candidate pools**.
   They are source-group disjoint before sampling, but they are not yet a test
   set or a training set.
2. Blind-review a stratified random 200-row subset of the gold pool on all five
   axes. This is the only set eligible to become the frozen ML acceptance test.
3. Blind-review an active 120-row subset of the train pool on Energy and
   Curiosity only. These labels target the two axes where hybrid currently
   retains an advantage; they are not five-axis training examples.
4. AMI is the immediate production-eligible source: it is CC BY 4.0, contains
   actual multi-party speech, and retains dialogue-act and speaker provenance.
5. Keep Speak & Improve 2025 as a research-only candidate. Its spontaneous L2
   learner speech and human CEFR/disfluency annotations are excellent for
   diagnostics, but its non-commercial access terms prevent it from entering a
   Pally product-training set without written permission.
6. Do not add HCRC rows to a production training set until its archive and
   current-page license conflict is resolved in writing.

## ML Acceptance Gate

Switch the runtime default to `ml` only when a frozen human-reviewed,
source-group-held-out test set shows all of the following:

- ML average MAE is no worse than hybrid by more than `0.20`.
- ML average Spearman is at least hybrid's average Spearman.
- No axis is worse than hybrid by more than `0.03` Spearman.
- The result repeats after changing the held-out source groups.

Then set `PALLY_AXIS_ANALYZER=ml` and retain `hybrid` as a reversible config
fallback for one monitored release.

## Candidate Pools And Annotation Sets

The first required data collection is ready. It uses new utterances only and
excludes any text already present in the 3,137-row experimental dataset.

| Set | Rows | Source mix | Use |
|---|---:|---|---|
| Gold candidate reservoir | 600 | 200 NICT, 200 AMI, 200 Taskmaster | Held-out candidate pool only |
| Train candidate reservoir | 1,200 | 400 NICT, 400 AMI, 400 Taskmaster | Candidate pool for active learning only |
| Gold blind-review set | 200 | 68 NICT, 67 AMI, 65 Taskmaster | Stratified-random five-axis acceptance test after review |
| Train active-review set | 120 | 54 NICT, 30 AMI, 36 Taskmaster | Energy/Curiosity calibration labels after review |

The two candidate reservoirs are group-disjoint: the 600 gold rows span 377
interview, meeting, or conversation groups; the 1,200 train rows span 742
different groups; there are zero overlapping source groups and zero
normalized-text duplicates between them.

Energy and Curiosity are marginally balanced in each candidate reservoir. Because strong,
high-energy questions are genuinely scarce in the learner corpus, the four
cross-buckets use a `1:3:3:1` allocation rather than forcing low-quality rows
into the scarce high-energy/high-curiosity cell:

| Focus bucket | Gold | Train |
|---|---:|---:|
| High Energy, High Curiosity | 75 | 150 |
| High Energy, Low Curiosity | 225 | 450 |
| Low Energy, High Curiosity | 225 | 450 |
| Low Energy, Low Curiosity | 75 | 150 |

The final annotation sets preserve the pool-level group separation: the 120
active rows use 120 source groups, the 200 gold rows use 161 source groups, and
they share no source group. The gold sampler uses only source, length band,
question form, and the retained pseudo-stratum metadata. It does not use ML,
hybrid, rule, or draft labels.

The train sampler fits the current experimental ML model solely to rank useful
human checks. It selects 40 Energy disagreements, 40 Curiosity disagreements,
15 Energy extremes, 15 Curiosity extremes, and 10 seeded random controls. The
selection reasons and predicted scores remain internal candidate metadata and
never appear in the reviewer CSV.

Files to review now:

- `data/fixtures/ml_transition_gold_candidates_600.jsonl`
- `data/fixtures/ml_transition_train_candidates_1200.jsonl`
- `data/fixtures/ml_transition_gold_stratified_candidates_200.jsonl`
- `data/fixtures/ml_transition_gold_blind_review_200.csv`
- `data/fixtures/ml_transition_train_active_ec_candidates_120.jsonl`
- `data/fixtures/ml_transition_train_active_ec_review_120.csv`

The review CSV files expose only a review ID, the utterance, adjacent text
context when available, applicable score columns, reviewer ID, completion
status, and notes. They intentionally omit source, source group, record ID,
focus bucket, draft labels, model predictions, and selection reasons. A
reviewer fills the score columns, supplies a reviewer ID, and sets
`review_status` to `completed`.

The previous 600-row and 1,200-row review CSV exports are superseded candidate
pool artifacts. Do not use them for annotation.

After a CSV is complete, convert it without changing its held-out role:

```powershell
.\.venv\Scripts\python.exe scripts\build_human_reviewed_axis_dataset.py `
  --input data\fixtures\ml_transition_gold_blind_review_200.csv `
  --candidates data\fixtures\ml_transition_gold_stratified_candidates_200.jsonl `
  --output data\fixtures\ml_transition_gold_human_200.jsonl `
  --axes all

.\.venv\Scripts\python.exe scripts\build_human_reviewed_axis_dataset.py `
  --input data\fixtures\ml_transition_train_active_ec_review_120.csv `
  --candidates data\fixtures\ml_transition_train_active_ec_candidates_120.jsonl `
  --output data\fixtures\ml_transition_train_human_ec_120.jsonl `
  --axes energy-curiosity
```

The 120-row output deliberately contains only Energy and Curiosity labels.
Extend the ML trainer with per-axis partial-label support before using it in a
five-axis fit; do not silently fill the other three axes with AI drafts.

## Reproducible Commands

```powershell
$rawNict='data\NICT_JLE_4.1\NICT_JLE_4.1\LearnerOriginal'
.\.venv\Scripts\python.exe scripts\extract_nict_jle.py $rawNict `
  --output data\fixtures\nict_jle_learner_utterances.jsonl

.\.venv\Scripts\python.exe scripts\sample_ml_transition_candidates.py

.\.venv\Scripts\python.exe scripts\select_ml_transition_annotation_sets.py

.\.venv\Scripts\python.exe scripts\export_axis_review_csv.py `
  --input data\fixtures\ml_transition_train_active_ec_candidates_120.jsonl `
  --output data\fixtures\ml_transition_train_active_ec_review_120.csv `
  --review-set train --axes energy-curiosity

.\.venv\Scripts\python.exe scripts\export_axis_review_csv.py `
  --input data\fixtures\ml_transition_gold_stratified_candidates_200.jsonl `
  --output data\fixtures\ml_transition_gold_blind_review_200.csv `
  --review-set gold --axes all

$env:PALLY_AXIS_DATASET='data\fixtures\axis_dataset_combined_real_speech_experimental.jsonl'
.\.venv\Scripts\python.exe ai\evaluate_axis_analyzers.py --word-ngram-max 2 --mode source-group-holdout
Remove-Item Env:\PALLY_AXIS_DATASET
```
