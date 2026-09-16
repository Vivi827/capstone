# -*- coding: utf-8 -*-
"""Days 1-3 diagnosis: rerun rule / ML / hybrid on dev-200 with a training set
purged of every dev-200 canonical group.

Cycle-4 DECISION AGREED #3: 100 of the 200 dev rows share a canonical training
group, and `evaluate_axis_analyzers.py --mode gold-holdout` does not enforce
group exclusion. This script measures how much that leak inflates the numbers
by comparing, on the SAME dev-200 test set:

  * full experimental training (3,137 rows)
  * training purged of every dev-200 canonical group (NICT provenance
    recovered first via source_line)

for rule, ML (unigram + bigram), and hybrid, NA-aware, with per-source and
per-reviewer slices.

No human labels are created. The reserved final pool is not opened. dev-200
labels are used for evaluation only, never for training.

Run from the repository root:
  python scripts/diagnose_dev200_group_purge.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.analyzers import RuleBasedAxisAnalyzer
from ai.contracts import AXIS_KEYS
from ai.ml_baseline import AxisTrainingExample, TfidfKnnAxisRegressor, _validate_axes
from scripts.reserve_ml_transition_final_pool import (
    canonical_group,
    recover_nict_training_groups,
    training_group_set,
)

TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"
NICT_RAW_PATH = Path(ROOT) / "data" / "fixtures" / "nict_jle_learner_utterances.jsonl"
GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


def _spearman(exp: list[float], pred: list[float]) -> float:
    return _pearson(_rank(exp), _rank(pred))


def _as_examples(rows: list[dict[str, Any]]) -> list[AxisTrainingExample]:
    out = []
    for r in rows:
        try:
            label = _validate_axes(r["axes"])
        except (KeyError, ValueError):
            continue
        out.append(
            AxisTrainingExample(
                utterance=str(r["utterance"]),
                label=label,
                style=str(r.get("style", "conversation")),
                source=str(r.get("source", "")),
                source_group=str(r.get("source_group", "")),
            )
        )
    return out


def _predict_rule(gold: list[dict[str, Any]]) -> list[dict[str, int]]:
    rule = RuleBasedAxisAnalyzer()
    return [rule.analyze(r["utterance"]).to_axes_dict() for r in gold]


def _predict_ml(train: list[AxisTrainingExample], gold: list[dict[str, Any]], ngram: int) -> list[dict[str, int]]:
    model = TfidfKnnAxisRegressor(word_ngram_max=ngram).fit(train, require_full_axes=True)
    return [model.predict(r["utterance"]) for r in gold]


def _blend(rule_p: list[dict[str, int]], ml_p: list[dict[str, int]]) -> list[dict[str, int]]:
    return [{a: round((rp[a] + mp[a]) / 2) for a in AXIS_KEYS} for rp, mp in zip(rule_p, ml_p)]


def _score(gold: list[dict[str, Any]], preds: list[dict[str, int]], indices: list[int] | None = None) -> dict[str, Any]:
    idx = indices if indices is not None else list(range(len(gold)))
    per_axis_mae: dict[str, float] = {}
    per_axis_rho: dict[str, float] = {}
    for axis in AXIS_KEYS:
        exp = [float(gold[i]["axes"][axis]) for i in idx if axis in gold[i]["axes"]]
        prd = [float(preds[i][axis]) for i in idx if axis in gold[i]["axes"]]
        if not exp:
            continue
        per_axis_mae[axis] = sum(abs(p - e) for e, p in zip(exp, prd)) / len(exp)
        per_axis_rho[axis] = _spearman(exp, prd)
    valid_rho = [v for v in per_axis_rho.values() if not math.isnan(v)]
    na = [a for a, v in per_axis_rho.items() if math.isnan(v)]
    return {
        "n": len(idx),
        "mae": sum(per_axis_mae.values()) / len(per_axis_mae),
        "rho": (sum(valid_rho) / len(valid_rho)) if valid_rho else float("nan"),
        "rho_na_axes": na,
        "per_axis_mae": per_axis_mae,
        "per_axis_rho": per_axis_rho,
    }


def _fmt(s: dict[str, Any]) -> str:
    rho = "n/a" if math.isnan(s["rho"]) else f"{s['rho']:.3f}"
    na = f"  (rho n/a: {', '.join(s['rho_na_axes'])})" if s["rho_na_axes"] else ""
    return f"MAE {s['mae']:6.3f}   rho {rho:>6} over {len(s['per_axis_rho']) - len(s['rho_na_axes'])}/5{na}"


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    nict_raw = load_jsonl(NICT_RAW_PATH)
    gold = load_jsonl(GOLD_PATH)

    print("=== baseline / exclusion ledger ===")
    print(f"training      {TRAIN_PATH.name}  sha256={file_sha256(TRAIN_PATH)}  rows={len(train_rows)}")
    print(f"nict_raw      {NICT_RAW_PATH.name}  sha256={file_sha256(NICT_RAW_PATH)}  rows={len(nict_raw)}")
    print(f"gold_dev_200  {GOLD_PATH.name}  sha256={file_sha256(GOLD_PATH)}  rows={len(gold)}")

    nict_groups, nict_stats = recover_nict_training_groups(train_rows, nict_raw)
    provenance_ok = nict_stats.get("verified", 0) == nict_stats.get("nict_training_rows", -1)
    print(f"nict provenance recovery: {nict_stats}  ok={provenance_ok}")
    if not provenance_ok:
        raise SystemExit("NICT provenance incomplete -- purge would be unsound, aborting")

    train_groups = training_group_set(train_rows, nict_groups)
    dev_groups = {canonical_group(r) for r in gold}
    overlap = dev_groups & train_groups
    print(f"dev-200 canonical groups: {len(dev_groups)}   overlapping a training group: {len(overlap)}")

    dev_overlap_idx = [i for i, r in enumerate(gold) if canonical_group(r) in train_groups]
    dev_clean_idx = [i for i, r in enumerate(gold) if canonical_group(r) not in train_groups]
    print(f"dev rows overlapping training: {len(dev_overlap_idx)}  "
          f"{dict(Counter(gold[i]['source'] for i in dev_overlap_idx))}")
    print(f"dev rows not overlapping     : {len(dev_clean_idx)}  "
          f"{dict(Counter(gold[i]['source'] for i in dev_clean_idx))}")

    # purge training rows whose canonical group is any dev-200 group
    def _row_group(r: dict[str, Any]) -> str:
        if str(r.get("source", "")).startswith("nict"):
            sl = r.get("source_line")
            if sl is not None and 0 <= int(sl) - 1 < len(nict_raw):
                raw = nict_raw[int(sl) - 1]
                if str(raw["utterance"]).strip() == str(r["utterance"]).strip():
                    return canonical_group(raw)
        return canonical_group(r)

    purged = [r for r in train_rows if _row_group(r) not in dev_groups]
    print(f"\ntraining rows: full {len(train_rows)}  ->  dev-group-purged {len(purged)}  "
          f"(removed {len(train_rows) - len(purged)})")
    print(f"  removed by source: {dict(Counter(r['source'] for r in train_rows if _row_group(r) in dev_groups))}")

    full_ex = _as_examples(train_rows)
    purged_ex = _as_examples(purged)
    print(f"  usable full-label training examples: full {len(full_ex)}  purged {len(purged_ex)}")

    rule_p = _predict_rule(gold)

    print("\n=== dev-200 (all rows) ===")
    for label, train_ex in (("full-3137", full_ex), ("dev-group-purged", purged_ex)):
        for ngram in (1, 2):
            ml_p = _predict_ml(train_ex, gold, ngram)
            hy_p = _blend(rule_p, ml_p)
            tag = f"{label} / {'uni' if ngram == 1 else 'bi'}gram"
            print(f"  ML     [{tag:28}] {_fmt(_score(gold, ml_p))}")
            print(f"  hybrid [{tag:28}] {_fmt(_score(gold, hy_p))}")
    print(f"  rule   [{'(training-independent)':28}] {_fmt(_score(gold, rule_p))}")

    print("\n=== dev-200 split: overlapping vs non-overlapping training groups (bigram, purged ML) ===")
    ml_p = _predict_ml(purged_ex, gold, 2)
    hy_p = _blend(rule_p, ml_p)
    for slice_label, idx in (("overlap-100", dev_overlap_idx), ("clean-100", dev_clean_idx)):
        print(f"  [{slice_label}] rule   {_fmt(_score(gold, rule_p, idx))}")
        print(f"  [{slice_label}] ML     {_fmt(_score(gold, ml_p, idx))}")
        print(f"  [{slice_label}] hybrid {_fmt(_score(gold, hy_p, idx))}")

    print("\n=== per-source (purged bigram) ===")
    by_source: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(gold):
        by_source[r["source"]].append(i)
    for src, idx in sorted(by_source.items()):
        print(f"  [{src:26} n={len(idx):3}] rule {_fmt(_score(gold, rule_p, idx))}")
        print(f"  [{src:26} n={len(idx):3}] ML   {_fmt(_score(gold, ml_p, idx))}")
        print(f"  [{src:26} n={len(idx):3}] hyb  {_fmt(_score(gold, hy_p, idx))}")

    print("\n=== per-reviewer (purged bigram) ===")
    by_rev: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(gold):
        by_rev[str(r.get("reviewer_id", "unknown"))].append(i)
    for rev, idx in sorted(by_rev.items()):
        srcmix = dict(Counter(gold[i]["source"] for i in idx))
        print(f"  [{rev:14} n={len(idx):3} {srcmix}]")
        print(f"      rule {_fmt(_score(gold, rule_p, idx))}")
        print(f"      ML   {_fmt(_score(gold, ml_p, idx))}")
        print(f"      hyb  {_fmt(_score(gold, hy_p, idx))}")


if __name__ == "__main__":
    main()
