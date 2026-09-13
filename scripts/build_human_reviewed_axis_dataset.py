# -*- coding: utf-8 -*-
"""Convert a completed blind review CSV into labeled JSONL rows.

Two schemas, matching ``scripts/export_axis_review_csv.py``:

* legacy -- one CSV with ``review_id``, matched positionally to a candidate
  file. Output is one row per item.
* batch  -- one CSV per reviewer slot plus a manifest. Output is one *raw*
  row per (item, reviewer slot); aggregation and adjudication are a separate
  step (``scripts/aggregate_axis_reviews.py``) so raw scores stay immutable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


AXIS_KEYS = ("Formality", "Energy", "Intimacy", "Humor", "Curiosity")
REVIEW_AXES = {
    "all": AXIS_KEYS,
    "energy-curiosity": ("Energy", "Curiosity"),
    "energy-humor": ("Energy", "Humor"),
    "energy-curiosity-intimacy": ("Energy", "Curiosity", "Intimacy"),
}


class ReviewError(ValueError):
    pass


def parse_score(row: dict[str, str], row_number: int, axis: str) -> int:
    value = (row.get(f"reviewed_{axis}") or "").strip()
    if not value:
        raise ReviewError(f"row {row_number}: missing reviewed_{axis}")
    try:
        score = int(float(value))
    except ValueError as exc:
        raise ReviewError(f"row {row_number}: invalid reviewed_{axis}={value!r}") from exc
    if not 0 <= score <= 100:
        raise ReviewError(f"row {row_number}: reviewed_{axis} must be between 0 and 100")
    return score


def convert_row(
    row: dict[str, str],
    candidate: dict[str, Any],
    row_number: int,
    labeler: str,
    axes: str = "all",
) -> dict[str, Any]:
    if (row.get("review_status") or "").strip().lower() != "completed":
        raise ReviewError(f"row {row_number}: review_status must be completed")
    review_set = (row.get("review_set") or "").strip()
    if review_set not in {"gold", "train"}:
        raise ReviewError(f"row {row_number}: review_set must be gold or train")
    review_axes = REVIEW_AXES[axes]
    utterance = (row.get("utterance") or "").strip()
    if utterance != str(candidate.get("utterance", "")).strip():
        raise ReviewError(f"row {row_number}: utterance does not match its candidate record")
    return {
        "utterance": utterance,
        "axes": {axis: parse_score(row, row_number, axis) for axis in review_axes},
        "style": "conversation",
        "split": "test" if review_set == "gold" else "train",
        "notes": row.get("reviewer_notes", ""),
        "source": candidate.get("source", "unknown"),
        "source_group": candidate.get("source_group", ""),
        "source_record_id": candidate.get("source_record_id", ""),
        "focus_bucket": candidate.get("focus_bucket", ""),
        "label_status": "human_reviewed_blind",
        "labeler": labeler,
        "reviewer_id": row.get("reviewer_id", ""),
        "review_set": review_set,
        "review_axes": list(review_axes),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def candidate_index(rows: list[dict[str, Any]], review_set: str) -> dict[str, dict[str, Any]]:
    return {f"{review_set}-{index:04d}": row for index, row in enumerate(rows, start=1)}


def load_review_csv(
    path: Path,
    candidates: list[dict[str, Any]],
    labeler: str,
    axes: str = "all",
) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ReviewError("review CSV is empty")
    review_set = (rows[0].get("review_set") or "").strip()
    if review_set not in {"gold", "train"}:
        raise ReviewError("review CSV has an invalid review_set")
    if any((row.get("review_set") or "").strip() != review_set for row in rows):
        raise ReviewError("review CSV mixes review sets")
    indexed_candidates = candidate_index(candidates, review_set)
    converted: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        review_id = (row.get("review_id") or "").strip()
        if review_id in seen_ids:
            raise ReviewError(f"row {row_number}: duplicate review_id {review_id!r}")
        candidate = indexed_candidates.get(review_id)
        if candidate is None:
            raise ReviewError(f"row {row_number}: unknown review_id {review_id!r}")
        candidate_partition = str(candidate.get("review_partition", review_set)).strip()
        if candidate_partition != review_set:
            raise ReviewError(f"row {row_number}: candidate partition does not match review_set")
        seen_ids.add(review_id)
        converted.append(convert_row(row, candidate, row_number, labeler, axes))
    return converted


def write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _utterance_sha1(text: str) -> str:
    return hashlib.sha1(str(text).strip().encode("utf-8")).hexdigest()


def load_batch_reviews(
    slot_csv_paths: list[Path],
    manifest: dict[str, Any],
    candidates: list[dict[str, Any]],
    labeler: str,
) -> list[dict[str, Any]]:
    """Read one CSV per reviewer slot, validated against the manifest.

    Primary key is ``(annotation_batch, item_id, reviewer_slot)``. The same
    ``item_id`` appears once per slot; a repeat within one slot is an error.
    Output keeps every raw reviewer score (no averaging here).
    """
    annotation_batch = str(manifest["annotation_batch"])
    dataset_partition = str(manifest["dataset_partition"])
    scored_axes = tuple(manifest["scored_axes"])
    by_item = {item["item_id"]: item for item in manifest["items"]}
    candidate_by_index = {index: row for index, row in enumerate(candidates)}

    seen_keys: set[tuple[str, str, str]] = set()
    converted: list[dict[str, Any]] = []
    for path in slot_csv_paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ReviewError(f"{path.name}: review CSV is empty")
        for row_number, row in enumerate(rows, start=1):
            where = f"{path.name} row {row_number}"
            if (row.get("annotation_batch") or "").strip() != annotation_batch:
                raise ReviewError(f"{where}: annotation_batch != {annotation_batch!r}")
            if (row.get("review_status") or "").strip().lower() != "completed":
                raise ReviewError(f"{where}: review_status must be completed")
            item_id = (row.get("item_id") or "").strip()
            slot = (row.get("reviewer_slot") or "").strip()
            if not slot:
                raise ReviewError(f"{where}: missing reviewer_slot")
            if slot not in manifest["slots"]:
                raise ReviewError(f"{where}: reviewer_slot {slot!r} not in manifest slots {manifest['slots']}")
            item = by_item.get(item_id)
            if item is None:
                raise ReviewError(f"{where}: unknown item_id {item_id!r}")
            key = (annotation_batch, item_id, slot)
            if key in seen_keys:
                raise ReviewError(f"{where}: duplicate (batch, item_id, reviewer_slot) {key}")
            seen_keys.add(key)
            utterance = (row.get("utterance") or "").strip()
            if _utterance_sha1(utterance) != item["utterance_sha1"]:
                raise ReviewError(f"{where}: utterance does not match manifest item {item_id}")
            reviewer_id = (row.get("reviewer_id") or "").strip()
            if not reviewer_id:
                raise ReviewError(f"{where}: missing reviewer_id")
            candidate = candidate_by_index.get(item["candidate_index"], {})
            axes = {axis: parse_score(row, row_number, axis) for axis in scored_axes}
            converted.append(
                {
                    "utterance": utterance,
                    "axes": axes,
                    "label_source": {axis: "human" for axis in axes},
                    "style": "conversation",
                    "split": dataset_partition,
                    "dataset_partition": dataset_partition,
                    "annotation_batch": annotation_batch,
                    "item_id": item_id,
                    "reviewer_slot": slot,
                    "reviewer_id": reviewer_id,
                    "notes": row.get("reviewer_notes", ""),
                    "source": candidate.get("source", "unknown"),
                    "source_group": candidate.get("source_group", ""),
                    "source_record_id": candidate.get("source_record_id", ""),
                    "focus_bucket": candidate.get("focus_bucket", ""),
                    "label_status": "human_reviewed_blind_raw",
                    "labeler": labeler,
                    "review_axes": list(scored_axes),
                }
            )

    # Require completeness only for the slots actually supplied (a batch may be
    # imported before every reviewer has finished). Each supplied slot must
    # cover all items.
    supplied_slots = {slot for _, _, slot in seen_keys}
    expected = {
        (annotation_batch, item_id, slot)
        for slot in supplied_slots
        for item_id in by_item
    }
    missing = expected - seen_keys
    if missing:
        raise ReviewError(f"batch import missing {len(missing)} (item, slot) rows, e.g. {sorted(missing)[:3]}")
    return converted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True,
                        help="review CSV; repeat once per reviewer slot in batch mode")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--labeler", default="human_blind_review")
    parser.add_argument("--axes", choices=tuple(REVIEW_AXES), default="all")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="manifest JSON from export_axis_review_csv --annotation-batch (switches to batch mode)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            rows = load_batch_reviews(args.input, manifest, load_jsonl(args.candidates), args.labeler)
        else:
            if len(args.input) != 1:
                raise ReviewError("legacy mode takes exactly one --input (use --manifest for batch mode)")
            rows = load_review_csv(args.input[0], load_jsonl(args.candidates), args.labeler, args.axes)
    except ReviewError as exc:
        raise SystemExit(f"review CSV is not complete: {exc}") from exc
    write_jsonl(rows, args.output)
    print(f"rows={len(rows)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
