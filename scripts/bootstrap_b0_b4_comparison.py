# -*- coding: utf-8 -*-
"""Source-group-stratified paired bootstrap over the B0-B4 arms (cycle 4c/4d).

Reproduces Codex's exploratory bootstrap (cycle 4c CODEX_REVIEW.md section 5)
as a committed, rerunnable script, and reruns it on the POST-L2-FIX ridge
predictions (the original review ran it on the pre-fix predictions).

Method: group key = canonical_group(gold_row). For each source, resample its
own groups with replacement (same group count as observed), keep every row
in a selected group, reuse identical resampled indices across every arm so
the comparison is paired. Recompute the NA-aware mean Spearman rho per
resample. Report the observed paired difference and the 2.5/97.5 percentiles
of 1000 resamples.

This is a development-stage exploratory interval: it does not correct for
repeated dev-200 analysis, configuration selection (e.g. k/ngram sweep-max),
the nonblind reviewer-01 relabel, or rubric uncertainty. It is not a
final-gate confirmatory statistic (see docs/ml-transition-contract.md
section 9 for the frozen final protocol).

Run from the repository root:
  python scripts/bootstrap_b0_b4_comparison.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.analyzers import RuleBasedAxisAnalyzer
from ai.contracts import AXIS_KEYS
from ai.linear_axis_model import LinearAxisExample, RidgeAxisRegressor
from ai.ml_baseline import AxisTrainingExample, TfidfKnnAxisRegressor, _validate_axes
from scripts.reserve_ml_transition_final_pool import canonical_group, recover_nict_training_groups

TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"
NICT_RAW_PATH = Path(ROOT) / "data" / "fixtures" / "nict_jle_learner_utterances.jsonl"
GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"
FLASH_TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "flash_lite_train_purged_scores.jsonl"
FLASH_DEV_PATH = Path(ROOT) / "data" / "fixtures" / "flash_lite_dev200_scores.jsonl"
SEED = 20260912
REPS = 1000


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _rank(values: list[float]) -> list[float]:
    ordered = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        avg = (i + j + 2) / 2
        for _, oi in ordered[i : j + 1]:
            ranks[oi] = avg
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float | None:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def _row_group(row: dict[str, Any], nict_raw: list[dict[str, Any]]) -> str:
    if str(row.get("source", "")).startswith("nict"):
        sl = row.get("source_line")
        if sl is not None and 0 <= int(sl) - 1 < len(nict_raw):
            raw = nict_raw[int(sl) - 1]
            if str(raw["utterance"]).strip() == str(row["utterance"]).strip():
                return canonical_group(raw)
    return canonical_group(row)


def build_predictions() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, int]]]]:
    train_rows = load_jsonl(TRAIN_PATH)
    nict_raw = load_jsonl(NICT_RAW_PATH)
    gold = load_jsonl(GOLD_PATH)
    ng, st = recover_nict_training_groups(train_rows, nict_raw)
    if st.get("verified") != st.get("nict_training_rows"):
        raise SystemExit(f"NICT provenance incomplete: {st}")
    dev_groups = {canonical_group(r) for r in gold}
    purged = [r for r in train_rows if _row_group(r, nict_raw) not in dev_groups]

    draft_lin = [
        LinearAxisExample(str(r["utterance"]), {a: float(r["axes"][a]) for a in AXIS_KEYS}, str(r.get("source", "")))
        for r in purged if all(a in r["axes"] for a in AXIS_KEYS)
    ]
    flash_by_utt = {r["utterance"]: r["flash_lite_axes"] for r in load_jsonl(FLASH_TRAIN_PATH)}
    flash_lin = [
        LinearAxisExample(e.utterance, {a: float(flash_by_utt[e.utterance][a]) for a in AXIS_KEYS}, e.source)
        for e in draft_lin
    ]
    knn_ex = [
        AxisTrainingExample(str(r["utterance"]), _validate_axes(r["axes"]), "conversation", str(r.get("source", "")), "")
        for r in purged if all(a in r["axes"] for a in AXIS_KEYS)
    ]

    rule = RuleBasedAxisAnalyzer()
    rule_p = [rule.analyze(r["utterance"]).to_axes_dict() for r in gold]
    knn = TfidfKnnAxisRegressor(k=15, word_ngram_max=2).fit(knn_ex, require_full_axes=True)
    knn_p = [knn.predict(r["utterance"]) for r in gold]
    hybrid_p = [{a: round((rule_p[i][a] + knn_p[i][a]) / 2) for a in AXIS_KEYS} for i in range(len(gold))]
    ridge_draft = RidgeAxisRegressor(word_ngram_max=2).fit(draft_lin)
    ridge_draft_p = [ridge_draft.predict(r["utterance"]) for r in gold]
    ridge_flash = RidgeAxisRegressor(word_ngram_max=2).fit(flash_lin)
    ridge_flash_p = [ridge_flash.predict(r["utterance"]) for r in gold]
    flash_dev = {r["utterance"]: r["flash_lite_axes"] for r in load_jsonl(FLASH_DEV_PATH)}
    flash_direct_p = [flash_dev[r["utterance"]] for r in gold]

    arms = {
        "B0_rule": rule_p,
        "B1_kNN_draft": knn_p,
        "B2_hybrid": hybrid_p,
        "B3a_ridge_draft": ridge_draft_p,
        "B3b_ridge_flash": ridge_flash_p,
        "B4_flash_direct": flash_direct_p,
    }
    return gold, arms


def mean_rho(gold: list[dict[str, Any]], preds: list[dict[str, int]], idx: list[int]) -> float:
    vals = []
    for axis in AXIS_KEYS:
        expected = [float(gold[i]["axes"][axis]) for i in idx]
        predicted = [float(preds[i][axis]) for i in idx]
        rho = _pearson(_rank(expected), _rank(predicted))
        if rho is not None:
            vals.append(rho)
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> None:
    gold, arms = build_predictions()
    groups = [canonical_group(r) for r in gold]
    by_source_group: dict[str, dict[str, list[int]]] = {}
    for i, row in enumerate(gold):
        by_source_group.setdefault(row["source"], {}).setdefault(groups[i], []).append(i)
    sources = sorted(by_source_group)
    print(f"dev-200 rows={len(gold)}  groups={len(set(groups))}  sources={sources}")
    for src in sources:
        print(f"  {src}: {len(by_source_group[src])} groups")

    print("\nobserved mean rho:")
    for name, preds in arms.items():
        print(f"  {name:20} {mean_rho(gold, preds, list(range(len(gold)))):.4f}")

    pairs = [("B3a_ridge_draft", "B2_hybrid"), ("B3b_ridge_flash", "B2_hybrid"), ("B4_flash_direct", "B3b_ridge_flash")]
    rng = random.Random(SEED)
    diffs: dict[tuple[str, str], list[float]] = {pair: [] for pair in pairs}
    for _ in range(REPS):
        idx: list[int] = []
        for src in sources:
            gmap = by_source_group[src]
            keys = list(gmap.keys())
            chosen = [rng.choice(keys) for _ in range(len(keys))]
            for g in chosen:
                idx.extend(gmap[g])
        for a_name, b_name in pairs:
            diffs[(a_name, b_name)].append(mean_rho(gold, arms[a_name], idx) - mean_rho(gold, arms[b_name], idx))

    def pct(arr: list[float], q: float) -> float:
        ordered = sorted(arr)
        return ordered[int(q * (len(ordered) - 1))]

    print(f"\nsource-group-stratified paired bootstrap (seed={SEED}, reps={REPS}):")
    for a_name, b_name in pairs:
        d = diffs[(a_name, b_name)]
        observed = mean_rho(gold, arms[a_name], list(range(len(gold)))) - mean_rho(gold, arms[b_name], list(range(len(gold))))
        lo, hi = pct(d, 0.025), pct(d, 0.975)
        crosses_zero = lo < 0 < hi
        print(f"  {a_name} - {b_name}: observed {observed:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]"
              f"{'  <-- crosses zero, not distinguishable from no-improvement' if crosses_zero else ''}")

    print("\nThis is a development-stage exploratory interval on a repeatedly-analyzed dev")
    print("set, not a final-gate confirmatory statistic. See contract section 9.")


if __name__ == "__main__":
    main()
