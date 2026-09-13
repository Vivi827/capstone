# -*- coding: utf-8 -*-
"""Aggregate raw per-reviewer axis scores into per-item labels.

Input is the raw JSONL from ``build_human_reviewed_axis_dataset.py --manifest``
(one row per item per reviewer slot). This script never edits the raw file. It
writes:

* ``<output>``            -- one row per item with the aggregated label
* ``<output>.report.json`` -- inter-reviewer agreement stats + the list of
  items whose slot spread exceeds ``--disagreement-threshold``

An optional ``--adjudication`` JSON supplies a third-party resolution for
specific (item_id, axis) pairs. It is applied on top of the aggregate and
recorded in each affected row under ``adjudication``; the raw scores stay in
``raw_scores`` so the override is always auditable.

Aggregation keeps decimals (mean of the slot scores). Rounding to the model's
integer output space is a downstream concern, not done here.

Run from the repository root:
  python scripts/aggregate_axis_reviews.py --input raw.jsonl --output agg.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

AXIS_KEYS = ("Formality", "Energy", "Intimacy", "Humor", "Curiosity")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def aggregate(
    raw_rows: list[dict[str, Any]],
    adjudication: dict[str, dict[str, Any]],
    disagreement_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        by_item[str(row["item_id"])].append(row)

    axis_pair_abs: dict[str, list[float]] = defaultdict(list)
    flagged: list[dict[str, Any]] = []
    out_rows: list[dict[str, Any]] = []

    for item_id, rows in sorted(by_item.items()):
        slots = sorted({str(r["reviewer_slot"]) for r in rows})
        scored_axes = list(rows[0].get("review_axes") or AXIS_KEYS)
        raw_scores: dict[str, dict[str, float]] = {
            str(r["reviewer_slot"]): {axis: float(r["axes"][axis]) for axis in scored_axes if axis in r["axes"]}
            for r in rows
        }

        agg_axes: dict[str, float] = {}
        spreads: dict[str, float] = {}
        for axis in scored_axes:
            values = [raw_scores[s][axis] for s in slots if axis in raw_scores[s]]
            if not values:
                continue
            agg_axes[axis] = round(statistics.fmean(values), 2)
            spread = max(values) - min(values)
            spreads[axis] = spread
            if len(values) >= 2:
                # pairwise absolute difference; with 2 slots this is the spread
                axis_pair_abs[axis].append(spread)

        adj = adjudication.get(item_id, {})
        applied_adj: dict[str, Any] = {}
        for axis, resolved in adj.items():
            if axis == "note":
                continue
            if axis in agg_axes:
                applied_adj[axis] = {"from": agg_axes[axis], "to": float(resolved)}
                agg_axes[axis] = float(resolved)

        over = {axis: sp for axis, sp in spreads.items() if sp > disagreement_threshold}
        if over:
            flagged.append({"item_id": item_id, "spreads": over, "adjudicated": sorted(applied_adj)})

        first = rows[0]
        out_rows.append(
            {
                "utterance": first["utterance"],
                "axes": agg_axes,
                "label_source": {axis: "human_adjudicated" if axis in applied_adj else "human_mean" for axis in agg_axes},
                "style": first.get("style", "conversation"),
                "split": first.get("dataset_partition", first.get("split", "")),
                "dataset_partition": first.get("dataset_partition", ""),
                "annotation_batch": first.get("annotation_batch", ""),
                "item_id": item_id,
                "reviewer_slots": slots,
                "reviewer_ids": sorted({str(r["reviewer_id"]) for r in rows}),
                "raw_scores": raw_scores,
                "slot_spread": spreads,
                "adjudication": {"applied": applied_adj, "note": adj.get("note", "")} if adj else None,
                "source": first.get("source", "unknown"),
                "source_group": first.get("source_group", ""),
                "source_record_id": first.get("source_record_id", ""),
                "focus_bucket": first.get("focus_bucket", ""),
                "label_status": "human_reviewed_blind_aggregated",
                "review_axes": scored_axes,
            }
        )

    report = {
        "items": len(by_item),
        "raw_rows": len(raw_rows),
        "disagreement_threshold": disagreement_threshold,
        "per_axis_mean_abs_slot_diff": {
            axis: round(statistics.fmean(values), 2) for axis, values in sorted(axis_pair_abs.items()) if values
        },
        "per_axis_max_slot_diff": {
            axis: max(values) for axis, values in sorted(axis_pair_abs.items()) if values
        },
        "flagged_count": len(flagged),
        "flagged": flagged,
    }
    return out_rows, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="raw per-reviewer JSONL (immutable)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, default=None,
                        help="JSON: {item_id: {axis: resolved_value, note: str}}")
    parser.add_argument("--disagreement-threshold", type=float, default=15.0,
                        help="flag an item when a scored axis's slot spread exceeds this")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raw_rows = load_jsonl(args.input)
    adjudication = json.loads(args.adjudication.read_text(encoding="utf-8")) if args.adjudication else {}
    out_rows, report = aggregate(raw_rows, adjudication, args.disagreement_threshold)
    write_jsonl(out_rows, args.output)
    report_path = args.output.with_suffix(args.output.suffix + ".report.json") if args.output.suffix else args.output.with_name(args.output.name + ".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"items={report['items']} raw_rows={report['raw_rows']} flagged={report['flagged_count']}")
    print(f"per_axis_mean_abs_slot_diff={report['per_axis_mean_abs_slot_diff']}")
    print(f"output={args.output}")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
