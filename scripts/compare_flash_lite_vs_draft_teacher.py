# -*- coding: utf-8 -*-
"""Compare the Flash-Lite teacher and the draft_axes teacher against the
human gold labels on dev-200 (cycle 4b).

Reads `flash_lite_dev200_scores.jsonl` (from flash_lite_axis_teacher.py
--score) and `ml_transition_gold_human_200.jsonl`, runs `draft_axes` on the
same utterances, and reports per-axis MAE, signed bias, and Spearman for each
teacher vs the human gold, overall and per source. NA-aware.

This measures TEACHER quality against humans. It does not train anything and
does not by itself say a distilled student will improve -- that needs the
same-text retrain comparison.

Run from the repository root:
  python scripts/compare_flash_lite_vs_draft_teacher.py
"""

from __future__ import annotations

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

from ai.contracts import AXIS_KEYS
from scripts.draft_label_nict_jle_candidates import draft_axes

GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"
FLASH_PATH = Path(ROOT) / "data" / "fixtures" / "flash_lite_dev200_scores.jsonl"


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


def _axis_stats(human: list[float], pred: list[float]) -> tuple[float, float, float]:
    mae = sum(abs(p - h) for h, p in zip(human, pred)) / len(human)
    bias = sum(p - h for h, p in zip(human, pred)) / len(human)
    rho = _spearman(human, pred)
    return mae, bias, rho


def report(label: str, gold: list[dict[str, Any]], preds: dict[str, dict[str, int]], idx: list[int]) -> None:
    print(f"  {label}")
    maes, rhos = [], []
    for axis in AXIS_KEYS:
        h = [float(gold[i]["axes"][axis]) for i in idx]
        p = [float(preds[gold[i]["utterance"]][axis]) for i in idx]
        mae, bias, rho = _axis_stats(h, p)
        maes.append(mae)
        rho_s = "  n/a" if math.isnan(rho) else f"{rho:+.3f}"
        if not math.isnan(rho):
            rhos.append(rho)
        print(f"    {axis:<10} MAE {mae:6.2f}   bias {bias:+7.2f}   rho {rho_s}")
    mean_rho = sum(rhos) / len(rhos) if rhos else float("nan")
    print(f"    {'MEAN':<10} MAE {sum(maes) / len(maes):6.2f}                  rho "
          f"{'n/a' if math.isnan(mean_rho) else f'{mean_rho:+.3f}'} over {len(rhos)}/5")


def main() -> None:
    gold = load_jsonl(GOLD_PATH)
    flash_rows = load_jsonl(FLASH_PATH)
    flash_by_utt = {r["utterance"]: r["flash_lite_axes"] for r in flash_rows}

    missing = [g["utterance"] for g in gold if g["utterance"] not in flash_by_utt]
    if missing:
        print(f"WARNING: {len(missing)} dev utterances have no Flash-Lite score yet "
              f"(scoring still running?). Reporting on the {len(gold) - len(missing)} scored.")
    scored_idx = [i for i, g in enumerate(gold) if g["utterance"] in flash_by_utt]

    draft_by_utt = {g["utterance"]: draft_axes({"utterance": g["utterance"]}) for g in gold}

    print(f"\ndev-200 teacher-vs-human comparison ({len(scored_idx)} scored rows)\n")
    print("=== overall ===")
    report("draft_axes  vs human", gold, draft_by_utt, scored_idx)
    report("flash-lite  vs human", gold, flash_by_utt, scored_idx)

    by_source: dict[str, list[int]] = defaultdict(list)
    for i in scored_idx:
        by_source[gold[i]["source"]].append(i)
    for src, idx in sorted(by_source.items()):
        print(f"\n=== {src}  (n={len(idx)}) ===")
        report("draft_axes  vs human", gold, draft_by_utt, idx)
        report("flash-lite  vs human", gold, flash_by_utt, idx)

    print("\nReading: if flash-lite's per-axis rho beats draft_axes on the axes where ML is")
    print("weak (Energy/Taskmaster, Intimacy everywhere) and its bias is smaller, a distilled")
    print("or direct Flash-Lite analyzer is worth pursuing. Teacher gain != student gain.")


if __name__ == "__main__":
    main()
