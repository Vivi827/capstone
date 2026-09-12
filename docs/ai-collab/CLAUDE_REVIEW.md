# CLAUDE_REVIEW — cycle 4d Round 1

Substance is in `CONTEXT.md` (written together this round since this is
Claude reporting its own follow-up work, not responding to a prior AI
claim). Summary of what changed since cycle 4c closed:

1. Fixed the ridge L2 regularization bug (commit `ec04458`).
2. Reran the bootstrap on post-fix predictions (commit `6c322ce`) --
   **neither ridge candidate clears hybrid at 95% confidence now.**
3. Ran a vocabulary-matched ridge-vs-kNN ablation (17,913 features, matching
   kNN exactly): ridge still wins, 0.4202 vs kNN's 0.3624.
4. Nested group-holdout selection for k/ngram is running in the background;
   result will be shared once done (not yet available at the time this
   round was opened).

Open questions for you are listed in `CURRENT_TASK.md`'s "Round 2 지시".
The one I most want your independent judgment on is #3 there: how to
handle B3b's Formality bias without creating new dev-200 leakage. I do not
have a clean answer and do not want to invent one unilaterally since it
is a methodology choice with a real tradeoff (accuracy on one axis vs.
further burning the dev set).
