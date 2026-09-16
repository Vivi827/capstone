# CURRENT TASK — cycle 4b: Day 1 results + Days 2-9 diagnosis

## User goals (fixed, ranked)

1. Minimize human labeling work.
2. Transition to ML (make it the runtime analyzer).
3. Every step must have a sound, documented justification.

## Status

DECISION cycle 4 accepted. User decisions recorded:
- U1 (keep human-gold gate vs change goal to "reproduce teacher"): **defer to
  post-diagnosis**. Gate stays default meanwhile.
- U2: **calibration on hold**, redesign to 30x2 in Days 3-5, do not distribute
  the 4x90 files.

Claude is executing Days 2-9 and consulting Codex at checkpoints. This round:
review Day 1 results and the Days 2-3 experiment design.

## Day 1 result (committed 219ae06, scripts/diagnose_dev200_group_purge.py)

- dev-200: 100/200 rows share a training canonical group. Purging (removes 197
  training rows, 158 AMI) moves dev-200 aggregates <0.07 MAE / <0.01 rho.
- non-overlapping 100: ML rho 0.282 vs rule 0.385 / hybrid 0.388; ML worst MAE
  16.14.
- per-source (purged bigram): AMI rho rule 0.291 / ML 0.130 / hybrid 0.272;
  Taskmaster 0.345 / 0.216 / 0.330 (Humor NA); NICT 0.292 / 0.355 / 0.368.
- Humor constant (rho NA) for all 65 Taskmaster rows and all 100 reviewer-01
  rows.

Claude's reading: ML overfits NICT-style learner speech (training-dominant),
does not generalize to AMI meetings or Taskmaster task-dialog. Points more to
coverage/representation than to teacher-label error. Not yet confirmed.

## Round 2 지시 (Codex)

Read `docs/ai-collab/CONTEXT.md`, `CLAUDE_REVIEW.md` (Day 1 results + Days 2-3
plan), and the cycle-4 `DECISION.md` sections it references.

1. Do the Day 1 numbers support "ML overfits NICT, generalization is the
   bottleneck"? What confound could produce the same per-source pattern
   (e.g. AMI rows are shorter meeting fragments; Taskmaster Humor is
   genuinely always ~0)? Verify against repo data.
2. Review Claude's Days 2-3 experiment design in CLAUDE_REVIEW.md section 2.
   For each experiment: is it the right test, what is the confound, what
   result would be decisive vs merely suggestive.
3. Given user goal #1 (minimize human labeling) and #2 (reach ML), what is
   the shortest credible path? Specifically: is there a version of "train on
   automated labels, evaluate on the existing reserved pool with a small
   human eval" that reaches goal #2 with justification, and how small can the
   human eval be while still supporting the gate?
4. Flag any Day 2-3 experiment that is not worth the time given the Day 1
   result.
5. Name every remaining point that needs a user decision before ML can
   become the runtime default, in order.

Write to `docs/ai-collab/CODEX_REVIEW.md` ONLY. Verify against real repo data.
Do not commit, push, or reset git state. Do not open the reserved pool.
