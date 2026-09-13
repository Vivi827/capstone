# -*- coding: utf-8 -*-
"""Build the train first-40 annotation candidate set (batch B3).

Draws 40 rows from ``ml_transition_train_active_ec_candidates_120.jsonl`` with
a fixed reason x source allocation -- it does NOT take the first 40 of the
file, because that file's order is the sampler's ranking and would over-weight
whichever reason sorts first.

Allocation (fixed here, recorded in the manifest):

  selection_reason        share of 120   -> first40 quota
  energy_disagreement          40              13
  curiosity_disagreement       40              13
  energy_extreme               15               5
  curiosity_extreme            15               5
  random_control               10               4
                                              ----
                                               40

Within each reason the quota is split across sources in proportion to that
reason's own source mix in the 120-row file, largest-remainder rounded, then
rows are picked deterministically by ``sha256(seed | source_record_id)``.

Axes for review: Energy, Curiosity, Intimacy. The other 80 rows can get an
empty CSV too (``--all-remaining``) but must not be scored until the
calibration disagreement review is done and the rubric is frozen.

Run from the repository root:
  python scripts/build_train_first40_set.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("data/fixtures/ml_transition_train_active_ec_candidates_120.jsonl")
DEFAULT_FIRST40 = Path("data/fixtures/ml_transition_train_first40_candidates.jsonl")
DEFAULT_REMAINDER = Path("data/fixtures/ml_transition_train_active_remainder_candidates.jsonl")
DEFAULT_SEED = 20260910

REASON_QUOTA = {
    "energy_disagreement": 13,
    "curiosity_disagreement": 13,
    "energy_extreme": 5,
    "curiosity_extreme": 5,
    "random_control": 4,
}
REVIEW_AXES = ("Energy", "Curiosity", "Intimacy")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("source_record_id") or row.get("conversation_id") or row["utterance"])


def _rank(rows: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: hashlib.sha256(f"{seed}|{_row_key(r)}".encode()).hexdigest())


def largest_remainder(counts: dict[str, int], total: int) -> dict[str, int]:
    pool = sum(counts.values())
    if pool == 0:
        return {key: 0 for key in counts}
    exact = {key: value * total / pool for key, value in counts.items()}
    floor = {key: int(value) for key, value in exact.items()}
    remaining = total - sum(floor.values())
    order = sorted(counts, key=lambda k: (exact[k] - floor[k], counts[k]), reverse=True)
    for key in order[:remaining]:
        floor[key] += 1
    return floor


def select_first40(rows: list[dict[str, Any]], seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_reason[str(row.get("selection_reason", "unknown"))].append(row)

    selected: list[dict[str, Any]] = []
    plan: dict[str, Any] = {}
    for reason, quota in REASON_QUOTA.items():
        available = by_reason.get(reason, [])
        source_counts = Counter(str(r["source"]) for r in available)
        per_source = largest_remainder(dict(source_counts), quota)
        plan[reason] = {"quota": quota, "available": len(available), "per_source": per_source}
        for source, take in per_source.items():
            pool = _rank([r for r in available if str(r["source"]) == source], seed)
            if take > len(pool):
                raise SystemExit(f"{reason}/{source}: need {take} rows, only {len(pool)} available")
            selected.extend(pool[:take])

    if len(selected) != sum(REASON_QUOTA.values()):
        raise SystemExit(f"selected {len(selected)} rows, expected {sum(REASON_QUOTA.values())}")

    selected_keys = {_row_key(r) for r in selected}
    remainder = [r for r in rows if _row_key(r) not in selected_keys]
    manifest = {
        "seed": seed,
        "reason_quota": REASON_QUOTA,
        "review_axes": list(REVIEW_AXES),
        "plan": plan,
        "selected": len(selected),
        "remainder": len(remainder),
        "selected_source_mix": dict(Counter(str(r["source"]) for r in selected)),
    }
    return selected, {"remainder": remainder, "manifest": manifest}


def _tag(row: dict[str, Any], batch: str) -> dict[str, Any]:
    tagged = dict(row)
    tagged["annotation_batch"] = batch
    tagged["dataset_partition"] = "train"
    tagged["review_axes"] = list(REVIEW_AXES)
    # keep the sampler's original id mapping so re-numbering never mislinks
    tagged["origin_candidate_key"] = _row_key(row)
    return tagged


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--first40-output", type=Path, default=DEFAULT_FIRST40)
    parser.add_argument("--remainder-output", type=Path, default=DEFAULT_REMAINDER)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = load_jsonl(args.input)
    if len(rows) != 120:
        print(f"warning: expected 120 active-EC rows, got {len(rows)}")

    selected, extra = select_first40(rows, args.seed)
    first40 = [_tag(row, "first40") for row in selected]
    remainder = [_tag(row, "first40_remainder") for row in extra["remainder"]]

    write_jsonl(first40, args.first40_output)
    write_jsonl(remainder, args.remainder_output)
    manifest_path = args.first40_output.with_name(args.first40_output.stem + ".plan.json")
    manifest_path.write_text(json.dumps(extra["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(extra["manifest"], ensure_ascii=False, indent=2))
    print(f"first40_output={args.first40_output}  ({len(first40)} rows)")
    print(f"remainder_output={args.remainder_output}  ({len(remainder)} rows, scoring on hold)")
    print(f"plan={manifest_path}")


if __name__ == "__main__":
    main()
