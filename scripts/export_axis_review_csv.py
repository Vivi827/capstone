# -*- coding: utf-8 -*-
"""Export source-blind review CSV files from real-speech candidates.

Two schemas:

* legacy  -- ``--review-set gold|train`` emits one CSV with ``review_id``
  columns, matched back positionally by ``build_human_reviewed_axis_dataset``.
  Kept for the already-collected gold-200 / train-120 sets.

* batch   -- ``--annotation-batch calibration|pilot|first40`` emits one blind
  CSV *per reviewer slot* plus a non-blind manifest. Columns follow
  docs/ml-transition-contract.md section 5:
  ``annotation_batch, dataset_partition, item_id, reviewer_slot`` +
  score columns + ``reviewer_id, review_status, reviewer_notes``. Item order
  is shuffled independently per slot under a recorded seed so two reviewers
  never see each other's scores or the same row order.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

AXIS_KEYS = ("Formality", "Energy", "Intimacy", "Humor", "Curiosity")

AXIS_SETS: dict[str, tuple[str, ...]] = {
    "all": AXIS_KEYS,
    "energy-curiosity": ("Energy", "Curiosity"),
    "energy-humor": ("Energy", "Humor"),
    "energy-curiosity-intimacy": ("Energy", "Curiosity", "Intimacy"),
}

# reviewer slots are letters; slot count picks the prefix of this tuple.
SLOT_LETTERS = ("A", "B", "C", "D")

BATCH_PARTITION_HINT = {
    "calibration": "train",
    "pilot": "train",
    "first40": "train",
}


def axis_columns(axes: str) -> tuple[str, ...]:
    if axes not in AXIS_SETS:
        raise ValueError(f"unsupported review axes: {axes}")
    return AXIS_SETS[axes]


# --- legacy schema -----------------------------------------------------------

LEGACY_BASE = ("review_set", "review_id", "utterance", "previous_turn", "next_turn")
LEGACY_TAIL = ("reviewer_id", "review_status", "reviewer_notes")


def legacy_fields(axes: str) -> tuple[str, ...]:
    return LEGACY_BASE + tuple(f"reviewed_{axis}" for axis in axis_columns(axes)) + LEGACY_TAIL


def legacy_row(row: dict[str, Any], review_set: str, index: int, axes: str = "all") -> dict[str, str]:
    scored = axis_columns(axes)
    return {
        "review_set": review_set,
        "review_id": f"{review_set}-{index:04d}",
        "utterance": str(row["utterance"]),
        "previous_turn": str(row.get("previous_turn") or ""),
        "next_turn": str(row.get("next_turn") or ""),
        **{f"reviewed_{axis}": "" for axis in scored},
        "reviewer_id": "",
        "review_status": "pending",
        "reviewer_notes": "",
    }


# Back-compat aliases for the pre-batch API (used by tests and older callers).
REVIEW_FIELDS = legacy_fields("all")
ENERGY_CURIOSITY_FIELDS = legacy_fields("energy-curiosity")
review_row = legacy_row
review_fields = legacy_fields


def write_legacy_csv(rows: list[dict[str, Any]], review_set: str, output_path: Path, axes: str) -> None:
    fields = legacy_fields(axes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(legacy_row(row, review_set, index, axes) for index, row in enumerate(rows, start=1))


# --- batch schema ----------------------------------------------------------

# Batch review CSVs show the current utterance only, to match the model's
# input (contract section 4). previous_turn / next_turn stay in the manifest
# for reference but are never put in front of the reviewer here.
BATCH_BASE = (
    "annotation_batch",
    "dataset_partition",
    "item_id",
    "reviewer_slot",
    "utterance",
)
BATCH_TAIL = ("reviewer_id", "review_status", "reviewer_notes")


def batch_fields(axes: str) -> tuple[str, ...]:
    return BATCH_BASE + tuple(f"reviewed_{axis}" for axis in axis_columns(axes)) + BATCH_TAIL


def _utterance_sha1(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()


def build_manifest(
    candidates: list[dict[str, Any]],
    *,
    annotation_batch: str,
    dataset_partition: str,
    axes: str,
    slots: list[str],
    seed: int,
) -> dict[str, Any]:
    scored = axis_columns(axes)
    items = [
        {
            "item_id": f"{annotation_batch}-{index:04d}",
            "candidate_index": index - 1,
            "utterance": str(row["utterance"]),
            "utterance_sha1": _utterance_sha1(str(row["utterance"])),
            "previous_turn": str(row.get("previous_turn") or ""),
            "next_turn": str(row.get("next_turn") or ""),
        }
        for index, row in enumerate(candidates, start=1)
    ]
    slot_order: dict[str, list[str]] = {}
    for slot in slots:
        order = [item["item_id"] for item in items]
        random.Random(f"{seed}|{annotation_batch}|{slot}").shuffle(order)
        slot_order[slot] = order
    return {
        "annotation_batch": annotation_batch,
        "dataset_partition": dataset_partition,
        "axes": axes,
        "scored_axes": list(scored),
        "seed": seed,
        "slots": slots,
        "item_count": len(items),
        "items": items,
        "slot_order": slot_order,
    }


def write_batch_csvs(manifest: dict[str, Any], output_path: Path) -> list[Path]:
    """One blind CSV per slot: ``<stem>.slot<Slot>.csv``. Manifest goes to
    ``<stem>.manifest.json`` and is NOT blind (holds the candidate mapping)."""
    fields = batch_fields(manifest["axes"])
    scored = manifest["scored_axes"]
    by_id = {item["item_id"]: item for item in manifest["items"]}
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for slot in manifest["slots"]:
        slot_path = output_path.with_suffix("")
        slot_path = slot_path.with_name(f"{slot_path.name}.slot{slot}.csv")
        with slot_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item_id in manifest["slot_order"][slot]:
                item = by_id[item_id]
                writer.writerow(
                    {
                        "annotation_batch": manifest["annotation_batch"],
                        "dataset_partition": manifest["dataset_partition"],
                        "item_id": item_id,
                        "reviewer_slot": slot,
                        "utterance": item["utterance"],
                        **{f"reviewed_{axis}": "" for axis in scored},
                        "reviewer_id": "",
                        "review_status": "pending",
                        "reviewer_notes": "",
                    }
                )
        written.append(slot_path)

    manifest_path = output_path.with_suffix("")
    manifest_path = manifest_path.with_name(f"{manifest_path.name}.manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(manifest_path)
    return written


# --- cli -----------------------------------------------------------------------


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--axes", choices=tuple(AXIS_SETS), default="all")
    # legacy
    parser.add_argument("--review-set", choices=("gold", "train"), default=None)
    # batch
    parser.add_argument("--annotation-batch", choices=("calibration", "pilot", "first40"), default=None)
    parser.add_argument("--dataset-partition", choices=("train", "dev", "test"), default=None)
    parser.add_argument("--reviewers", type=int, default=2, help="reviewer slot count for the batch schema")
    parser.add_argument("--seed", type=int, default=20260910, help="per-slot shuffle seed, recorded in the manifest")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = load_jsonl(args.input)

    if args.annotation_batch:
        if args.review_set:
            raise SystemExit("choose either --review-set (legacy) or --annotation-batch (batch), not both")
        if not 1 <= args.reviewers <= len(SLOT_LETTERS):
            raise SystemExit(f"--reviewers must be between 1 and {len(SLOT_LETTERS)}")
        partition = args.dataset_partition or BATCH_PARTITION_HINT[args.annotation_batch]
        slots = list(SLOT_LETTERS[: args.reviewers])
        manifest = build_manifest(
            rows,
            annotation_batch=args.annotation_batch,
            dataset_partition=partition,
            axes=args.axes,
            slots=slots,
            seed=args.seed,
        )
        written = write_batch_csvs(manifest, args.output)
        print(f"rows={len(rows)} slots={','.join(slots)} partition={partition} seed={args.seed}")
        for path in written:
            print(f"  wrote {path}")
        return

    if not args.review_set:
        raise SystemExit("legacy export needs --review-set gold|train (or use --annotation-batch)")
    write_legacy_csv(rows, args.review_set, args.output, args.axes)
    print(f"rows={len(rows)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
