# -*- coding: utf-8 -*-
"""B1+ experiment: does a linear (ridge) student on Flash-Lite labels beat
hybrid on dev-200? (cycle 4b)

Compares, on dev-200 (dev-group-purged training, NA-aware, per source):
  rule
  hybrid (rule + kNN on draft_axes labels)          -- current best local
  kNN     student  on draft_axes labels              -- current ML
  ridge   student  on draft_axes labels              -- isolates model family
  ridge   student  on Flash-Lite labels              -- B1+ candidate
  Flash-Lite direct                                  -- teacher ceiling

`--flash-train PATH` : JSONL from flash_lite_axis_teacher.py --score over the
                       purged training texts. If absent, the Flash-Lite arms
                       are skipped.

No human labels created. dev-200 for evaluation only. Reserved pool untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.analyzers import RuleBasedAxisAnalyzer
from ai.contracts import AXIS_KEYS
from ai.linear_axis_model import LinearAxisExample, RidgeAxisRegressor
from ai.ml_baseline import AxisTrainingExample, TfidfKnnAxisRegressor, _validate_axes
from scripts.reserve_ml_transition_final_pool import canonical_group, recover_nict_training_groups, training_group_set

TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"
NICT_RAW_PATH = Path(ROOT) / "data" / "fixtures" / "nict_jle_learner_utterances.jsonl"
GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"


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


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


def _spearman(e: list[float], p: list[float]) -> float:
    return _pearson(_rank(e), _rank(p))


def _score(gold: list[dict[str, Any]], preds: list[dict[str, int]], idx: list[int]) -> dict[str, Any]:
    per_mae: dict[str, float] = {}
    per_rho: dict[str, float] = {}
    for axis in AXIS_KEYS:
        e = [float(gold[i]["axes"][axis]) for i in idx]
        p = [float(preds[i][axis]) for i in idx]
        per_mae[axis] = sum(abs(pp - ee) for ee, pp in zip(e, p)) / len(e)
        per_rho[axis] = _spearman(e, p)
    valid = [v for v in per_rho.values() if not math.isnan(v)]
    na = [a for a, v in per_rho.items() if math.isnan(v)]
    return {
        "mae": sum(per_mae.values()) / len(per_mae),
        "rho": sum(valid) / len(valid) if valid else float("nan"),
        "na": na,
        "per_rho": per_rho,
        "per_mae": per_mae,
    }


def _fmt(s: dict[str, Any]) -> str:
    rho = "n/a" if math.isnan(s["rho"]) else f"{s['rho']:.3f}"
    na = f" (na {','.join(s['na'])})" if s["na"] else ""
    return f"MAE {s['mae']:6.2f}  rho {rho:>6}{na}"


def _row_group(row: dict[str, Any], nict_raw: list[dict[str, Any]]) -> str:
    if str(row.get("source", "")).startswith("nict"):
        sl = row.get("source_line")
        if sl is not None and 0 <= int(sl) - 1 < len(nict_raw):
            raw = nict_raw[int(sl) - 1]
            if str(raw["utterance"]).strip() == str(row["utterance"]).strip():
                return canonical_group(raw)
    return canonical_group(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flash-train", type=Path, default=Path(ROOT) / "data" / "fixtures" / "flash_lite_train_purged_scores.jsonl")
    parser.add_argument("--ngram", type=int, default=2, choices=(1, 2))
    parser.add_argument("--knn-k", type=int, default=15)
    args = parser.parse_args()

    train_rows = load_jsonl(TRAIN_PATH)
    nict_raw = load_jsonl(NICT_RAW_PATH)
    gold = load_jsonl(GOLD_PATH)
    ng, st = recover_nict_training_groups(train_rows, nict_raw)
    if st.get("verified") != st.get("nict_training_rows"):
        raise SystemExit(f"NICT provenance incomplete: {st}")
    dev_groups = {canonical_group(r) for r in gold}
    purged = [r for r in train_rows if _row_group(r, nict_raw) not in dev_groups]
    print(f"purged training rows: {len(purged)}")

    # --- draft_axes-labelled students ---
    draft_knn_ex = [
        AxisTrainingExample(str(r["utterance"]), _validate_axes(r["axes"]), str(r.get("style", "conversation")), str(r.get("source", "")), str(r.get("source_group", "")))
        for r in purged if all(a in r["axes"] for a in AXIS_KEYS)
    ]
    draft_lin_ex = [
        LinearAxisExample(str(r["utterance"]), {a: float(r["axes"][a]) for a in AXIS_KEYS}, str(r.get("source", "")))
        for r in purged if all(a in r["axes"] for a in AXIS_KEYS)
    ]

    rule = RuleBasedAxisAnalyzer()
    rule_p = [rule.analyze(r["utterance"]).to_axes_dict() for r in gold]

    knn = TfidfKnnAxisRegressor(k=args.knn_k, word_ngram_max=args.ngram).fit(draft_knn_ex, require_full_axes=True)
    knn_p = [knn.predict(r["utterance"]) for r in gold]
    hybrid_p = [{a: round((rule_p[i][a] + knn_p[i][a]) / 2) for a in AXIS_KEYS} for i in range(len(gold))]

    print("  fitting ridge (draft_axes labels)...")
    ridge_draft = RidgeAxisRegressor(word_ngram_max=args.ngram).fit(draft_lin_ex)
    ridge_draft_p = [ridge_draft.predict(r["utterance"]) for r in gold]

    arms: dict[str, list[dict[str, int]]] = {
        "rule": rule_p,
        f"kNN(draft, k{args.knn_k})": knn_p,
        "hybrid(rule+kNN draft)": hybrid_p,
        "ridge(draft)": ridge_draft_p,
    }

    # --- Flash-Lite-labelled students ---
    if args.flash_train.exists():
        flash_rows = load_jsonl(args.flash_train)
        flash_by_utt = {r["utterance"]: r["flash_lite_axes"] for r in flash_rows}
        flash_lin_ex = [
            LinearAxisExample(str(r["utterance"]), {a: float(flash_by_utt[r["utterance"]][a]) for a in AXIS_KEYS}, str(r.get("source", "")))
            for r in purged if r["utterance"] in flash_by_utt
        ]
        print(f"  Flash-Lite training labels available for {len(flash_lin_ex)}/{len(purged)} purged rows")
        if len(flash_lin_ex) >= 200:
            print("  fitting ridge (Flash-Lite labels)...")
            ridge_flash = RidgeAxisRegressor(word_ngram_max=args.ngram).fit(flash_lin_ex)
            arms["ridge(flash-lite)"] = [ridge_flash.predict(r["utterance"]) for r in gold]

            flash_knn_ex = [
                AxisTrainingExample(e.utterance, {a: int(round(e.label[a])) for a in AXIS_KEYS}, "conversation", e.source, "")
                for e in flash_lin_ex
            ]
            knn_flash = TfidfKnnAxisRegressor(k=args.knn_k, word_ngram_max=args.ngram).fit(flash_knn_ex, require_full_axes=True)
            arms[f"kNN(flash-lite, k{args.knn_k})"] = [knn_flash.predict(r["utterance"]) for r in gold]

        # Flash-Lite direct on dev, if scored
        dev_flash_path = Path(ROOT) / "data" / "fixtures" / "flash_lite_dev200_scores.jsonl"
        if dev_flash_path.exists():
            dev_flash = {r["utterance"]: r["flash_lite_axes"] for r in load_jsonl(dev_flash_path)}
            if all(r["utterance"] in dev_flash for r in gold):
                arms["flash-lite direct"] = [dev_flash[r["utterance"]] for r in gold]
    else:
        print(f"  (no {args.flash_train.name} yet -- Flash-Lite arms skipped)")

    by_source: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(gold):
        by_source[r["source"]].append(i)
    all_idx = list(range(len(gold)))

    print("\n=== dev-200 overall ===")
    for name, preds in arms.items():
        print(f"  {name:28} {_fmt(_score(gold, preds, all_idx))}")

    for src, idx in sorted(by_source.items()):
        print(f"\n=== {src} (n={len(idx)}) ===")
        for name, preds in arms.items():
            print(f"  {name:28} {_fmt(_score(gold, preds, idx))}")

    print("\nPer-axis rho (overall):")
    print(f"  {'arm':28} " + "  ".join(f"{a[:4]:>6}" for a in AXIS_KEYS))
    for name, preds in arms.items():
        s = _score(gold, preds, all_idx)
        cells = []
        for a in AXIS_KEYS:
            v = s["per_rho"][a]
            cells.append("   n/a" if math.isnan(v) else f"{v:+.3f}")
        print(f"  {name:28} " + "  ".join(f"{c:>6}" for c in cells))


if __name__ == "__main__":
    main()
