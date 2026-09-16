# DECISION — cycle 4d: NICT provenance correction, Energy regression, hold on B3b (Round 3 synthesis)

2026-09-12. Claude Round 1 + Codex Round 2 (verified reproductions + one
high-priority provenance correction) + Claude verification. Development
finding only. No gate/runtime/labeling change follows automatically.

## Confirmed this round

1. **CONFIRMED, HIGH PRIORITY — the "208 NICT rows were human-edited" claim
   is wrong.** Direct check: `nict_jle_labeled_human_600.jsonl` (600 rows)
   is byte-identical to `nict_jle_labeled_draft_600.jsonl` on all 600 rows;
   every row's `labeler` field is `codex_accept_draft_per_user`
   (auto-accepted draft, not an independent human edit). The 208-row
   discrepancy found in the Day 2 teacher-fidelity check is
   `draft_axes()`'s CURRENT code output differing from the HISTORICALLY
   STORED draft label (rubric/code drift over time), not evidence of any
   human review. **Correction: the 3,137-row experimental training set
   contains zero independently human-verified axis labels for NICT (and,
   per its `ai_draft_needs_human_review` status, none for
   AMI/CHiME6/HCRC/Taskmaster either).** The only independent human labels
   anywhere in this project are gold-200 (dev) and the still-unopened
   176-row reserved pool (test). This must be corrected in
   `docs/ml-transition-diagnosis-log.md` sections 2 and 12 and in
   `scripts/diagnose_teacher_fidelity.py`'s docstring/output before any
   further reuse of the old claim.

2. **CONFIRMED — the vocabulary-matched ablation reproduces exactly**
   (kNN 0.3624 vs matched-vocab ridge 0.4202 vs capped-vocab ridge 0.4278,
   all at 17,913 vs 4,000 features respectively). Codex additionally
   verified the two implementations' IDF dictionaries are byte-identical
   and found zero feature-value differences across all 2,940 training rows
   -- the comparison is clean on the feature side. Caveat: matched ridge
   does not dominate every axis (Humor rho 0.075 < kNN's 0.119), and this
   result is one fixed-seed, fixed-epoch SGD run, not a converged/repeated
   estimate.

3. **CONFIRMED — the post-fix bootstrap reproduces exactly** and the
   resampling design (whole canonical groups, with replacement, per source,
   same indices reused across arms) is appropriate for a paired
   source-stratified cluster bootstrap, conditional on canonical groups
   being the right independence unit (unverified: no check for recurring
   speakers/higher-level relationships across groups). Confirmed
   qualifications to add before any report: the interval omits
   training/seed variation and the 15-cell k/ngram selection; a zero-crossing
   interval means "unresolved," not "no benefit"; the positive B4-B3b
   interval supports only that one pairwise contrast, not general B4
   superiority.

4. **CONFIRMED, GATE-RELEVANT — B3b's Energy regression is large.**
   Post-fix: B3b Energy rho 0.344 vs B2 (hybrid) 0.426, a drop of 0.082 --
   larger than the contract's per-axis 0.03 regression tolerance at the
   point estimate (not yet a formal final-test failure since this is dev,
   not the reserved pool, but a real problem to explain before any further
   B3b investment). Rule alone is still best on Energy at 0.505.

5. **CORRECTED — several §12 numbers in the diagnosis log are stale**
   (computed pre-L2-fix): Energy rho for B3b was reported as 0.389, is now
   0.344; B3b AMI MAE was reported as 12.64, is now 12.47; the claim "B3b
   beats B4 on pooled Intimacy rho" is false post-fix (0.337 < 0.359); B3b
   does still beat B4 on Humor (0.236 > 0.201). Fix these in the log.

6. **DELIVERED — nested group-holdout k/ngram selection.** Inner 80/20
   group split of the purged training set (seed
   `inner-nested-selection-20260912`, 2,305 inner-train / 635 inner-holdout
   rows), all 15 k x n-gram cells scored against the inner holdout's weak
   labels (never touching dev-200 for selection), winner k=15/trigram at
   inner-holdout rho 0.492. Refit that single winner on the full purged set
   and evaluated ONCE on dev-200: **rho 0.354**, versus the dev-selected max
   of 0.362 (k=15/bigram). The gap is small (~0.01) -- the dev-max figure
   was only mildly optimistic here, not badly inflated. Use 0.354 as the
   more honestly-obtained B1 estimate in any report; note 0.362 alongside it
   as the (mildly) selection-optimistic number actually used to configure
   B3a/B3b/B2 in this cycle.

## Formality bias -- what to do (Codex's recommendation, Claude concurs)

Per-source detail (new, not previously reported): B3b Formality bias is
**AMI +17.2, NICT +18.6, Taskmaster +9.9** -- not one uniform constant, so a
single scalar correction is not obviously adequate even if attempted.

Options evaluated:
- **(a) Leave uncorrected, hold, decide later with the reserved-176 pool
  as ONE frozen candidate's pass/fail** -- Codex's recommended default.
  Do not turn the final-gate/reproduction split into a calibration
  playground; that would demote it to dev under contract sections 9-11.
- (b) Calibrate against already-scored training data -- **not available**:
  per finding #1, there is no independent human anchor anywhere in the
  training pool to calibrate against. The "208 NICT edits" would have been
  this anchor and it does not exist.
- (c) Split dev-200 into a calibration slice and a reporting slice --
  possible but only as explicitly exploratory; both slices have already
  informed diagnosis and model choice, so it is not a clean retrospective
  holdout, and it further shrinks an already-strained dev set.
- (d) **A small, new, targeted human Formality-only labeling round** on
  non-reserved, non-dev, already-teacher-scored training groups, blind,
  frozen rubric, with some overlap to check agreement, held out of student
  fitting -- the only option that produces a genuine independent anchor.
  **This requires new human labeling and is a real tradeoff against goal 1
  (minimize human labeling). This is a USER DECISION, not Claude's or
  Codex's to make.**

**Decision this cycle: (a), by default.** Report B3b's Formality (and
Energy) defects honestly as unresolved; do not fabricate a correction from
data that turns out not to be independent. (d) is offered to the user as
the only path to actually fixing it, at the cost of some new labeling.

## B3b deployment adapter

**Hold**, per Codex: not because the bootstrap alone disqualifies ridge
(the contract's gate is not "beat hybrid's mean rho at 95%" alone -- it
also has MAE noninferiority and per-axis limits), but because there is a
concrete, unresolved, gate-relevant problem (Energy regression) plus the
uncorrected Formality defect. Building a serialization/deployment adapter
now would be effort spent on a candidate not yet worth freezing. Revisit
after: Formality path decided (a/d above), Energy regression explained or
fixed, nested-selection result available, and per-axis/per-source tables
are complete.

## USER DECISION POINTS (in order)

1. **Formality/Energy fix path.** Accept option (a) -- report both defects
   as open, do not fix now, decide with the reserved pool later (default,
   no new labeling) -- or authorize option (d), a small new human
   Formality-only labeling round (new labeling work, trades against goal 1,
   but is the only way to actually correct the defect before a final
   decision).
2. **U1 (unchanged, still pending from cycle 4b):** keep the human-gold
   acceptance gate vs. change the goal to "reproduce a teacher" -- now with
   the added fact that NO teacher in this project currently has any
   independent human backing either, which weakens the case for a
   teacher-reproduction goal specifically.
3. Whether to keep iterating on B3b (representation/seed/epoch tuning,
   different label mixtures) before or instead of treating hybrid as the
   interim default, given neither ridge candidate has cleared hybrid with
   confidence yet.

## Not doing

- Not opening the reserved final pool.
- Not changing `PALLY_AXIS_ANALYZER`.
- Not building a B3b deployment adapter yet.
- Not calibrating Formality against the NICT "human" labels (confirmed not
  independent).
- Not treating this cycle's findings as a completed report -- diagnosis-log
  section 12 needs the stale-number and NICT-provenance corrections before
  circulation.
