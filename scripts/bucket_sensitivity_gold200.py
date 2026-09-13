# -*- coding: utf-8 -*-
"""Bucket-sensitivity check for the AI-draft teacher on the gold-200 dev set.

`scripts/diagnose_gold_vs_ai_draft.py` runs `draft_axes()` on the 200 gold
utterances with **no** `sample_bucket`, so every row falls back to the
default bucket. That is one assumption. This script quantifies how much the
diagnosis depends on it, in three parts, and it never trains on or writes any
label.

1. Sampler reproduction error (training rows only, no human labels).
   Two `classify_bucket` implementations exist:
     A. generic  -- scripts/sample_real_speech_label_candidates.classify_bucket(row)
     B. NICT     -- scripts/sample_nict_jle_label_candidates.classify_bucket(text)
   Only B was used to assign the 600 NICT training rows' stored
   `sample_bucket`. We re-run both and count how often each disagrees with
   the stored value. A large generic-vs-stored gap means "pick the generic
   classifier" is itself a modelling choice, not a neutral recovery.

2. Teacher reproduction error (training rows only, no human labels).
   Re-run `draft_axes({utterance, sample_bucket: stored})` on the NICT
   training rows and compare to their stored `axes`. Rows that differ show
   the stored labels are not a pure function of the current rubric + stored
   bucket (rubric drift or manual edits since dataset construction).

3. Assumption-conditional effect on the current dev set (gold-200).
   Score `draft_axes()` against the human gold labels under three bucket
   assumptions:
     default  -- no sample_bucket (current diagnose script behaviour)
     variantA -- generic classify_bucket for every row
     variantB -- NICT classifier for nict_jle_real rows, generic elsewhere
   Report per-axis Spearman and MAE for each, plus the delta from default.
   The takeaway is the *direction and size of movement* under each
   assumption -- not a confirmation of any single axis correlation number.

Run from the repository root:
  python scripts/bucket_sensitivity_gold200.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.contracts import AXIS_KEYS
from scripts.diagnose_gold_vs_ai_draft import _spearman, load_jsonl
from scripts.draft_label_nict_jle_candidates import draft_axes
from scripts.sample_nict_jle_label_candidates import classify_bucket as classify_bucket_nict
from scripts.sample_real_speech_label_candidates import classify_bucket as classify_bucket_generic

DEFAULT_GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"
DEFAULT_TRAINING_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"


def _mae(human: list[float], draft: list[float]) -> float:
    return sum(abs(d - h) for h, d in zip(human, draft)) / len(human)


def sampler_reproduction(training_rows: list[dict[str, Any]]) -> None:
    nict_rows = [
        row
        for row in training_rows
        if str(row.get("source", "")).startswith("nict") and row.get("sample_bucket")
    ]
    print(f"[1] Sampler reproduction error  (NICT training rows with a stored sample_bucket: {len(nict_rows)})")
    if not nict_rows:
        print("    no NICT rows carry a stored sample_bucket -- skipped")
        print()
        return

    generic_mismatch = Counter()
    nict_mismatch = Counter()
    for row in nict_rows:
        stored = str(row["sample_bucket"])
        got_generic = classify_bucket_generic({"utterance": row["utterance"]})
        got_nict = classify_bucket_nict(str(row["utterance"]))
        if got_generic != stored:
            generic_mismatch[(stored, got_generic)] += 1
        if got_nict != stored:
            nict_mismatch[(stored, got_nict)] += 1

    g_total = sum(generic_mismatch.values())
    n_total = sum(nict_mismatch.values())
    print(f"    variant A generic  vs stored : {g_total}/{len(nict_rows)} disagree ({g_total / len(nict_rows):.1%})")
    for (stored, got), count in generic_mismatch.most_common(6):
        print(f"        stored={stored:<22} -> generic={got:<22} x{count}")
    print(f"    variant B NICT     vs stored : {n_total}/{len(nict_rows)} disagree ({n_total / len(nict_rows):.1%})")
    for (stored, got), count in nict_mismatch.most_common(6):
        print(f"        stored={stored:<22} -> nict={got:<22} x{count}")
    print("    -> choosing the generic classifier is a modelling choice, not a neutral recovery of history.")
    print()


def teacher_reproduction(training_rows: list[dict[str, Any]]) -> None:
    nict_rows = [
        row
        for row in training_rows
        if str(row.get("source", "")).startswith("nict")
        and row.get("sample_bucket")
        and isinstance(row.get("axes"), dict)
    ]
    print(f"[2] Teacher reproduction error  (NICT training rows with stored axes + bucket: {len(nict_rows)})")
    if not nict_rows:
        print("    no eligible NICT rows -- skipped")
        print()
        return

    any_diff = 0
    per_axis_abs: dict[str, list[float]] = {axis: [] for axis in AXIS_KEYS}
    per_axis_rows_diff: Counter = Counter()
    for row in nict_rows:
        stored_axes = row["axes"]
        recon = draft_axes({"utterance": row["utterance"], "sample_bucket": row["sample_bucket"]})
        row_differs = False
        for axis in AXIS_KEYS:
            if axis not in stored_axes:
                continue
            delta = abs(int(recon[axis]) - int(stored_axes[axis]))
            per_axis_abs[axis].append(delta)
            if delta:
                row_differs = True
                per_axis_rows_diff[axis] += 1
        if row_differs:
            any_diff += 1

    print(f"    rows where re-run != stored (any axis): {any_diff}/{len(nict_rows)} ({any_diff / len(nict_rows):.1%})")
    for axis in AXIS_KEYS:
        deltas = per_axis_abs[axis]
        if not deltas:
            continue
        mae = sum(deltas) / len(deltas)
        print(f"        {axis:<10} rows_changed={per_axis_rows_diff[axis]:>3}  mean|delta|={mae:5.2f}  max|delta|={max(deltas):>3}")
    print("    -> stored NICT labels are not a pure function of (current draft_axes + stored bucket).")
    print()


def _assign_buckets(gold_rows: list[dict[str, Any]], mode: str) -> list[str | None]:
    assignments: list[str | None] = []
    for row in gold_rows:
        if mode == "default":
            assignments.append(None)
        elif mode == "variantA":
            assignments.append(classify_bucket_generic({"utterance": row["utterance"]}))
        elif mode == "variantB":
            if str(row.get("source", "")) == "nict_jle_real":
                assignments.append(classify_bucket_nict(str(row["utterance"])))
            else:
                assignments.append(classify_bucket_generic({"utterance": row["utterance"]}))
        else:
            raise ValueError(f"unknown mode {mode}")
    return assignments


def _score(gold_rows: list[dict[str, Any]], buckets: list[str | None]) -> dict[str, tuple[float, float]]:
    per_axis_human: dict[str, list[float]] = {axis: [] for axis in AXIS_KEYS}
    per_axis_draft: dict[str, list[float]] = {axis: [] for axis in AXIS_KEYS}
    for row, bucket in zip(gold_rows, buckets):
        payload = {"utterance": row["utterance"]}
        if bucket is not None:
            payload["sample_bucket"] = bucket
        draft = draft_axes(payload)
        for axis in AXIS_KEYS:
            if axis not in row["axes"]:
                continue
            per_axis_human[axis].append(float(row["axes"][axis]))
            per_axis_draft[axis].append(float(draft[axis]))
    out: dict[str, tuple[float, float]] = {}
    for axis in AXIS_KEYS:
        human = per_axis_human[axis]
        draft = per_axis_draft[axis]
        if not human:
            continue
        out[axis] = (_spearman(human, draft), _mae(human, draft))
    return out


def dev_sensitivity(gold_rows: list[dict[str, Any]]) -> None:
    print(f"[3] Assumption-conditional effect on gold-200 dev set  (rows: {len(gold_rows)})")
    modes = ["default", "variantA", "variantB"]
    scores = {mode: _score(gold_rows, _assign_buckets(gold_rows, mode)) for mode in modes}

    bucket_mix = {
        mode: Counter(b for b in _assign_buckets(gold_rows, mode) if b is not None) for mode in modes
    }
    for mode in ("variantA", "variantB"):
        print(f"    {mode} bucket mix: {dict(bucket_mix[mode].most_common())}")
    print()

    header = f"    {'Axis':<10} {'default rho/MAE':>18} {'variantA rho/MAE':>20} {'variantB rho/MAE':>20}"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for axis in AXIS_KEYS:
        if axis not in scores["default"]:
            continue
        cells = []
        for mode in modes:
            rho, mae = scores[mode][axis]
            rho_s = "n/a" if rho != rho else f"{rho:+.2f}"  # noqa: PLR0124 - NaN check
            cells.append(f"{rho_s} / {mae:5.2f}")
        print(f"    {axis:<10} {cells[0]:>18} {cells[1]:>20} {cells[2]:>20}")
    print()
    print("    delta from default (variant - default), positive rho = better rank agreement:")
    for axis in AXIS_KEYS:
        if axis not in scores["default"]:
            continue
        base_rho, base_mae = scores["default"][axis]
        parts = []
        for mode in ("variantA", "variantB"):
            rho, mae = scores[mode][axis]
            if base_rho == base_rho and rho == rho:
                parts.append(f"{mode}: d_rho={rho - base_rho:+.2f} d_MAE={mae - base_mae:+.2f}")
            else:
                parts.append(f"{mode}: d_rho=n/a d_MAE={mae - base_mae:+.2f}")
        print(f"        {axis:<10} " + "   ".join(parts))
    print()
    print("    Reading: the numbers move with the bucket assumption. Treat this as the")
    print("    direction and magnitude of movement on the current dev set, not as a")
    print("    confirmation of any single axis correlation value.")
    print()


def main() -> None:
    gold_rows = load_jsonl(DEFAULT_GOLD_PATH)
    training_rows = load_jsonl(DEFAULT_TRAINING_PATH)
    print(f"gold_path={DEFAULT_GOLD_PATH}  rows={len(gold_rows)}")
    print(f"training_path={DEFAULT_TRAINING_PATH}  rows={len(training_rows)}")
    print()
    sampler_reproduction(training_rows)
    teacher_reproduction(training_rows)
    dev_sensitivity(gold_rows)


if __name__ == "__main__":
    main()
