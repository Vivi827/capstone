# -*- coding: utf-8 -*-
"""Select the 60-item independent bias-calibration sample (cycle 4d, item d).

Purpose: the diagnosis found the 3,137-row experimental training set has
ZERO independently human-verified axis labels anywhere (the NICT
"human_reviewed" rows are byte-identical to their draft labels). B3b (ridge
trained on Flash-Lite labels) has a source-specific Formality bias
(AMI +17.2 / NICT +18.6 / Taskmaster +9.9) and an Energy regression vs
hybrid that cannot be corrected or even sized without an independent human
reference. This script selects a small, source-balanced, randomly sampled
set for that purpose.

Method:
  * Start from `ml_transition_train_purged_2940.jsonl` (already excludes
    every dev-200 canonical group).
  * One utterance per canonical group (never two items sharing a group).
  * Plain random selection within each source (seeded) -- NOT extremes,
    NOT disagreement-selected -- so the sample supports an unbiased mean
    (Flash-Lite minus human) estimate per source.
  * 20 items per source (AMI / NICT / Taskmaster) = 60 total.

The selected canonical groups are written to a side file so the B3b refit
can exclude them from training (this calibration sample must not leak into
what it is calibrating).

Run from the repository root:
  python scripts/build_bias_calibration_candidates.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("data/fixtures/ml_transition_train_purged_2940.jsonl")
DEFAULT_OUTPUT = Path("data/fixtures/ml_transition_bias_calib_candidates_60.jsonl")
DEFAULT_GROUPS_OUTPUT = Path("data/fixtures/ml_transition_bias_calib_groups.json")
DEFAULT_SEED = 20260912
PER_SOURCE = 20
SOURCES = ("ami_real", "nict_jle_real", "taskmaster1_woz_user_real")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def canonical_group(row: dict[str, Any]) -> str:
    source = str(row.get("source", "unknown"))
    group = row.get("source_group") or row.get("source_record_id") or row.get("source_file")
    if not group:
        return f"{source}:utt:{str(row['utterance']).strip().casefold()}"
    return f"{source}:{group}"


def select(rows: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault(canonical_group(row), []).append(row)

    selected: list[dict[str, Any]] = []
    for source in SOURCES:
        groups = sorted({canonical_group(r) for r in rows if r.get("source") == source})
        ordered = sorted(groups, key=lambda g: hashlib.sha256(f"{seed}|{g}".encode()).hexdigest())
        for group in ordered[:PER_SOURCE]:
            candidates = by_group[group]
            # deterministic "random" pick of one utterance within the group
            pick = min(candidates, key=lambda r: hashlib.sha256(f"{seed}|{group}|{r['utterance']}".encode()).hexdigest())
            selected.append(pick)
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups-output", type=Path, default=DEFAULT_GROUPS_OUTPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = load_jsonl(args.input)
    selected = select(rows, args.seed)
    if len(selected) != PER_SOURCE * len(SOURCES):
        raise SystemExit(f"expected {PER_SOURCE * len(SOURCES)} rows, got {len(selected)}")

    tagged = []
    for row in selected:
        item = dict(row)
        item["annotation_batch"] = "bias_calib"
        item["dataset_partition"] = "train"
        item["review_axes"] = ["Formality", "Energy", "Intimacy", "Humor", "Curiosity"]
        item["canonical_group"] = canonical_group(row)
        tagged.append(item)

    write_jsonl(tagged, args.output)
    groups = sorted({item["canonical_group"] for item in tagged})
    args.groups_output.write_text(json.dumps({"seed": args.seed, "groups": groups}, indent=2), encoding="utf-8")

    from collections import Counter
    print(f"selected {len(tagged)} items: {dict(Counter(r['source'] for r in tagged))}")
    print(f"canonical groups reserved for exclusion from training: {len(groups)}")
    print(f"candidates -> {args.output}")
    print(f"groups (for B3b retrain exclusion) -> {args.groups_output}")


if __name__ == "__main__":
    main()
