# CLAUDE_REVIEW — cycle 4b: Day 1 results + Days 2-3 experiment design

## 1. Day 1 results (scripts/diagnose_dev200_group_purge.py, committed 219ae06)

### 1.1 Group-leak magnitude

| training | dev-200 MAE (bi) | dev-200 mean rho (bi) |
|---|---:|---:|
| full 3,137 | 14.897 | 0.280 |
| dev-group-purged 2,940 | 14.966 | 0.284 |

Purge removes 197 rows (AMI 158 / NICT 33 / Taskmaster 6). Aggregate effect
< 0.07 MAE, < 0.01 rho. The leak is real (100/200 rows, 69 groups) but does
not explain ML's weakness. hybrid moves 14.262/0.386 -> 14.283/0.391.

### 1.2 overlap vs clean split (purged bigram ML)

| slice | rule rho | ML rho | hybrid rho | ML MAE |
|---|---:|---:|---:|---:|
| overlap-100 | 0.274 | 0.268 | 0.330 | 13.80 |
| clean-100 | 0.385 | 0.282 | 0.388 | 16.14 |

On genuinely held-out rows ML is clearly behind rule and hybrid on rank and
worst on MAE. The leak was flattering ML slightly.

### 1.3 per-source (purged bigram)

| source | n | rule rho | ML rho | hybrid rho | rule MAE | ML MAE |
|---|---:|---:|---:|---:|---:|---:|
| AMI | 67 | 0.291 | 0.130 | 0.272 | 11.76 | 13.50 |
| NICT | 68 | 0.292 | 0.355 | 0.368 | 16.12 | 14.67 |
| Taskmaster | 65 | 0.345 | 0.216 | 0.330 | 15.73 | 16.79 |

ML only competes on NICT (its training-dominant source). Humor rho is NA for
Taskmaster (all 65 Humor labels are 0).

### 1.4 per-reviewer (purged bigram)

- reviewer-avg (AMI 67 / NICT 33): rule rho 0.203, ML 0.247, hybrid 0.272
- reviewer-01 (Taskmaster 65 / NICT 35): rule rho 0.395, ML 0.304, hybrid
  0.397; Humor NA

Reviewer and source are confounded (reviewer-avg is AMI-heavy). Cannot
separate a reviewer effect from a source effect on dev-200 alone.

### 1.5 Claude's reading (to be challenged)

ML overfits NICT-style learner speech (2,199 AI-draft rows + 600 NICT
accepted + seed) and does not generalize to meeting (AMI) or task-dialog
(Taskmaster) speech. This points to training-data coverage and/or the kNN
representation, more than to teacher-label error. Not yet confirmed -- could
be confounded with AMI utterance length / genuine Humor sparsity.

## 2. Days 2-3 experiment design (for Codex review)

All on the dev-group-purged common training set. dev-200 for evaluation only.
Freeze: training SHA-256 23051000..., purged-row count 2,940, k, ngram,
comparators (fixed rule, fixed old hybrid). NA-aware. Paired
canonical-group bootstrap 95% / 10,000 / seed 20260910 where an interval is
claimed.

### E1 — teacher fidelity vs student capacity (the core discriminator)

Inside the purged training set, make a group-held-out split (same
`split_by_source_group` hash trick, or a fresh seed). Fit ML on the train
part, predict the held-out part, and measure agreement with the **stored
weak labels** (not human). Separately, run `draft_axes` on the same held-out
part and measure its agreement with the stored weak labels.

- If the student reproduces the stored weak labels well (say MAE <= 5,
  rho >= 0.8) but both are far from human on dev (<= 0.30), the supervision
  is the ceiling -> automating more of the same labels cannot help; a better
  teacher or human labels are needed.
- If the student cannot even reproduce its own training signal
  (rho << teacher-vs-stored), the kNN representation is the limit -> invest
  in representation before labels.

Confound to name: the stored NICT labels are themselves `codex_accept_draft`
(not independent), so "reproduces the weak labels" partly means "reproduces
draft_axes". Report `draft_axes`-vs-stored on NICT (221/600 differ, F/E only)
alongside.

### E2 — same-text label swap (teacher quality, isolated)

Take a fixed subset of purged training texts. Keep texts, membership, IDF,
and k fixed. Fit ML twice: once with the stored labels, once with `draft_axes`
recomputed with the correct per-row `sample_bucket`. Compare both students on
dev-200. This isolates label quality from every size/coverage/IDF change that
the 338/938/3,137 comparison confounds (Codex's Round 2 point).

### E3 — representation sweep (labels + texts fixed)

k in {3, 5, 9} x {unigram, bigram} on the purged training set, dev-200
per-source. Also one feature ablation: strip capitalization and collapse
repeated punctuation from BOTH training and dev inputs, refit, compare --
but only after checking whether the real STT/transcript inputs preserve caps
and punctuation (if they do not, the rule analyzer's caps/`!` signals are
already dead in production and that itself is a finding).

### E4 — source-stratified size curve (coverage, not causal)

Group-stratified subsamples of the purged weak data at 25 / 50 / 100 % (5
fixed seeds), seed + NICT-accepted held constant, evaluate per-source on
dev-200. Consistent per-source gains from more matched weak data favour
"automate and scale". Flat or AMI/Taskmaster-negative curves favour "the
weak data does not transfer".

### E5 — input-limitation audit (bounded, no new labels)

For dev-200: count rows where the target is constant within an axis, where
two dev rows have near-identical text but different human labels, and where
the current-utterance-only text plausibly under-determines a label a context
reader would give. This locates information gaps; it cannot prove a
text-only ceiling without a controlled human study (out of scope now).

## 3. Open questions for Codex

- E1: is "reproduce the weak labels" circular enough on NICT to be
  uninformative there? Should E1 be AMI/Taskmaster-only?
- E2: is recomputing `draft_axes` with the correct bucket a meaningful
  "better teacher", or just a different lexical heuristic? Is it worth doing
  before the Flash-Lite comparison?
- Shortest path to goal #2: if E1 says "supervision is the ceiling", does
  that force human labels, or is a single strong LLM teacher (Flash-Lite,
  rubric-guided, distilled) an acceptable justification for the gate given
  goal #1?
