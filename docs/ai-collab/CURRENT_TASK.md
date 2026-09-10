# CURRENT TASK — cycle 4: label strategy & calibration

## Goal

Converge on a concrete, ordered execution plan for the next ~2 weeks that:
1. does NOT pre-commit to large-scale human labeling,
2. maximizes what can be learned with zero or minimal new human labels,
3. keeps an honest, independent human evaluation path alive,
4. decides whether the 4x90 calibration runs now, later, or shrinks.

## Round 2 지시 (Codex)

Read `docs/ai-collab/CONTEXT.md` and `docs/ai-collab/CLAUDE_REVIEW.md`
(Claude's Round 1 response to your recommendation).

Your job this round:

1. Where Claude's Round 1 agrees with you, confirm or sharpen it.
2. Where Claude pushes back, either concede or defend with a concrete,
   checkable argument (name the file/script/number).
3. Answer these directly, with a recommended default for each:
   - (a) **Diagnosis-first plan**: list the specific zero-new-label
     experiments on dev-200 worth running, in priority order, and for each:
     what result would change the label-volume decision. Be concrete about
     what "the teacher is the bottleneck" vs "the model is the bottleneck"
     vs "text-only input is the bottleneck" would each look like in numbers.
   - (b) **Alternative LLM labeling**: concrete design for "a different-method
     LLM scoring vs the existing `draft_axes` teacher" comparison. Which
     model, what prompt structure, how many items, how to measure bias
     without calling AI-consensus a human label. Feasible under the
     GCP-only / Gemini-2.5-Flash-Lite MVP constraint?
   - (c) **first-40 as the pilot of human value**: exact before/after
     protocol. What is the training set before, what is it after, what
     metric on which dev split, what effect size would justify expanding
     human labeling and what would kill it.
   - (d) **Calibration now vs later vs smaller**: give a recommendation.
     If "later", state the precise trigger. If "smaller", give the number
     and the revised detection-probability it buys.
   - (e) **Independent eval set**: if training labels are fully automated,
     what is the minimum honest human evaluation that still supports a
     "better at reading human tone" claim? Does the reserved final pool
     (176/156) need human labels, and if so how many, by whom, when.
4. Flag anything in the already-built Phase 2 artifacts that becomes wrong
   or wasteful under a diagnosis-first plan.

Write your response to `docs/ai-collab/CODEX_REVIEW.md` ONLY. Do not modify
any other file. Do not commit, push, or reset git state. Verify claims
against real repo data where checkable rather than asserting.
