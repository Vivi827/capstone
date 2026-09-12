# CLAUDE_REVIEW — cycle 4c Round 1: self-audit before Codex check

I ran the B0-B4 experiment described in `CONTEXT.md` across this session.
Before asking Codex to check it, here is my own list of what I am NOT
confident is clean -- flagging these explicitly rather than waiting for
Codex to find them.

## Things I already suspect are weaknesses

1. **B1's quoted rho (0.362) is a selected maximum, not a single a priori
   run.** The k/n-gram sweep (`k in {3,5,7,9,15} x {1,2,3}-gram`) was run on
   dev-200 directly, and I reported the best cell. The same is implicitly
   true for B3a/B3b, which I ran with `k=15, bigram` for the kNN comparison
   arms because that was the sweep's winner. This means B1 and the kNN
   comparison arms are optimistically biased relative to a single
   pre-registered configuration. B0 (rule) and B4 (Flash-Lite) do not have
   this problem -- rule has no hyperparameters tuned on dev-200, and the
   Flash-Lite prompt was frozen before scoring (I did not iterate the prompt
   after seeing dev-200 results).

2. **Ridge hyperparameters (l2=1.0, lr=0.5, epochs=40, batch_size=32,
   min_df=2, max_features=4000) were picked once, a priori, and never
   varied against dev-200.** I believe this is clean but I have not written
   down anywhere *why* those specific values, so it reads as arbitrary even
   though it was not tuned.

3. **No confidence interval or significance test anywhere in this cycle.**
   Every comparison above is a point estimate on n=200 (n=67-68 per source,
   and n=100 or fewer once NA axes like Humor are dropped for a slice). I do
   not know how much of B2 (0.408) vs B3b (0.480) vs B4 (0.542) is outside
   noise.

4. **I have not re-verified, in this exact commit state, that the
   dev-group-purge used for B1/B3a/B3b's training set is still leak-free.**
   It was verified earlier in cycle 4b (`scripts/diagnose_dev200_group_purge.py`
   asserts 0 overlap after NICT provenance recovery), and I have not changed
   that logic, but I have not re-run the assertion since the reviewer-01
   re-review changed dev-200's *labels* (not its rows/groups, so the
   group-purge itself should be unaffected -- but this is exactly the kind
   of thing worth an independent re-check).

5. **`ai/linear_axis_model.py` is new code (this session) and only checked
   by inspecting its top-weighted features for face validity** (e.g.
   "please"/"could"/"would" raise Formality, "hey"/"!" lower it) -- I did not
   write a unit test for the gradient/update math itself, and there is no
   existing test suite coverage for it yet.

6. **B4's "cannot fully parallelize" latency claim** is based on reading
   `backend/main.py`'s current `/api/chat` handler (axis result feeds
   `compute_character` before the reply-generation call), not a measured
   round-trip in the deployed app.

## What I am fairly confident holds

- The headline ranking direction (B0 < B1 < B2 < B3a < B3b < B4) reproduced
  across two independent dev-200 states (before and after the reviewer-01
  re-review), which is at least mild evidence it isn't an artifact of one
  particular gold-200 snapshot.
- B3b is a genuine capacity increase over B1/B3a on the SAME underlying
  weak-label family in one case (B3a vs B1: same labels, different model,
  B3a wins) -- so the model-family effect and the teacher-quality effect
  were each isolated in at least one paired comparison.
- No human labels were fabricated; B4's LLM output was never written into
  dev-200 as if it were a human score.

Please check all six items above, plus anything else that looks wrong,
against the actual code and data.
