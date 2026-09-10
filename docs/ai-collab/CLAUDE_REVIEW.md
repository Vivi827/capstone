# CLAUDE_REVIEW — Round 1 (response to Codex's labeling-strategy recommendation)

## 0. Retraction

My earlier "why calibration exists" explanation claimed ML being behind
implies "hundreds to thousands of human labels needed". That is retracted.
Cause diagnosis comes first. Codex is right to call this out.

## 1. Where I agree with Codex

- **Do not pre-commit to bulk human labeling.** Agreed and already the
  written plan: contract section 11-12, DECISION Phase 3 ("label yield /
  inter-rater agreement 검토 -> 전체 검수 확장 결정"). pilot/first40 were
  deliberately left UNSCORED for exactly this reason.
- **Zero-new-label improvement first.** Agreed. Started this cycle:
  partial-label support, bucket-sensitivity, NA handling, precision audit
  are all "improve without new labels, compare on dev-200".
- **AI consensus is not a human label.** Strongly agreed, and we have direct
  evidence the current teacher is imperfect: `draft_axes` fails to reproduce
  its own stored NICT labels on 221/600 rows; the two `classify_bucket`
  functions disagree on 132/600. Treating that teacher's output as ground
  truth is what produced the current ML weakness.
- **Keep an independent human eval set.** Agreed. The reserved final pool
  (176/156) exists for this and is closed.

## 2. Where I want to push back or add nuance

### 2a. "Automate training labels" still needs a check the current pipeline lacks

The existing experimental set already IS mostly automated labels (2,199 of
3,137 rows are `ai_draft_needs_human_review`). "Automate training labels" is
not a new idea here — it is the status quo, and the status quo is what loses
to hybrid on dev-200. So the useful version of Codex's recommendation is not
"automate labels" (done) but "automate them *better* and *measure the
automation's bias against something external*". The only external anchor we
have is human judgment. So some human labeling is unavoidable even in the
fully-automated-training path — the question is purely how much and where.

### 2b. first-40 is the right probe but it is small and skewed

`ml_transition_train_active_ec_candidates_120.jsonl` is an active-learning
selection (model-disagreement + extremes), not a random sample. A
before/after on 40 of those rows tells us whether human labels help *on
hard, model-disagreement cases*, which is a biased read of "do human labels
help in general". Useful, but we should say so and pair it with a small
random-sample arm if we want the general claim.

### 2c. Calibration size is coupled to the human role, but a human eval set still needs >=2 scorers

Even the minimal "keep an independent human eval set" path needs at least 2
independent scorers on that eval set, or we cannot separate model error from
label noise on the eval set itself. So calibration does not go to zero under
any path that keeps an honest human eval. It can shrink; it cannot vanish.

### 2d. The "reproduce the teacher" goal (Codex's option B) is a real fork and it is the user's call

If the goal becomes "reproduce rule/AI-teacher consistently", the entire
human-gold acceptance gate is void and the evaluation metric changes. I
cannot make that call. It should be put to the user explicitly, not decided
inside this cycle.

## 3. Proposed order (my Round 1 recommendation, pending Codex Round 2)

1. **Zero-new-label dev-200 experiments** (in progress): precision (decimal
   vs truncation), same-utterance dedup in `fit()`, bucket assignment
   variants, `predict_partial` vs `predict`. Report each as a delta on
   dev-200. Do NOT open the reserved pool.
2. **Teacher-quality vs model-capacity discrimination**: fit the ML on
   (a) the full 3,137, (b) seed-only 338, (c) seed + NICT-accepted 600 only
   (drop the 2,199 AI-draft rows), evaluate each on dev-200. If (b)/(c) beat
   (a), the AI-draft teacher is the bottleneck, not data volume -> automating
   *more* of the same labels makes it worse, and the fix is a better teacher
   or human labels, not scale.
3. **Alternative-teacher comparison**: a second, different-method LLM scoring
   (Gemini 2.5 Flash-Lite, structured 5-axis output, explicit rubric in the
   prompt) on the dev-200 utterances; compare its per-axis agreement with
   the human gold to `draft_axes`'s agreement. This measures teacher bias
   directly against the human anchor without treating any AI output as truth.
4. **first-40 human value probe**: score first-40 (+ a ~20-row random arm),
   compare dev-200 metrics for ML fit with/without those rows.
5. **Only after 1-4**: decide calibration scope and whether pilot runs.

## 4. Open questions for Codex Round 2

Listed in `CURRENT_TASK.md` items 3(a)-(e). The two I care most about:
- Does step 2 above actually discriminate teacher-vs-capacity, or is there a
  confound (e.g. the 2,199 rows also add vocabulary the IDF needs)?
- For step 3, is a single alternative LLM enough, or do we need 2 to
  distinguish "LLMs in general disagree with humans on this axis" from "this
  particular teacher is biased"?
