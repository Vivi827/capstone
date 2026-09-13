# -*- coding: utf-8 -*-

import csv
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.aggregate_axis_reviews import aggregate
from scripts.build_human_reviewed_axis_dataset import ReviewError, convert_row, load_batch_reviews
from scripts.export_axis_review_csv import (
    ENERGY_CURIOSITY_FIELDS,
    REVIEW_FIELDS,
    build_manifest,
    review_row,
    write_batch_csvs,
)


def test_blind_review_row_has_no_draft_axes() -> None:
    row = review_row(
        {
            "utterance": "Could you explain that again?",
            "source": "ami_real",
            "source_group": "meeting-1",
            "source_record_id": "act-1",
        },
        "gold",
        1,
    )

    assert tuple(row) == REVIEW_FIELDS
    assert all(row[f"reviewed_{axis}"] == "" for axis in ("Formality", "Energy", "Intimacy", "Humor", "Curiosity"))
    assert row["review_status"] == "pending"
    assert "axes" not in row
    assert "focus_bucket" not in row
    assert row["previous_turn"] == ""
    assert row["next_turn"] == ""
    assert "source" not in row
    assert "source_group" not in row
    assert "source_record_id" not in row


def test_energy_curiosity_review_row_exposes_only_requested_axes() -> None:
    row = review_row({"utterance": "Could you explain that again?"}, "train", 1, "energy-curiosity")

    assert tuple(row) == ENERGY_CURIOSITY_FIELDS
    assert set(row) >= {"reviewed_Energy", "reviewed_Curiosity"}
    assert "reviewed_Formality" not in row


def test_completed_review_row_becomes_labeled_test_example() -> None:
    row = {
        "review_set": "gold",
        "utterance": "Could you explain that again?",
        "reviewed_Formality": "45",
        "reviewed_Energy": "30",
        "reviewed_Intimacy": "35",
        "reviewed_Humor": "5",
        "reviewed_Curiosity": "85",
        "reviewer_id": "reviewer-a",
        "review_status": "completed",
        "reviewer_notes": "Clear request for explanation.",
    }

    candidate = {
        "utterance": "Could you explain that again?",
        "source": "ami_real",
        "source_group": "meeting-1",
        "source_record_id": "act-1",
        "focus_bucket": "low_energy_high_curiosity",
    }
    converted = convert_row(row, candidate, 1, "human_blind_review")

    assert converted["split"] == "test"
    assert converted["axes"]["Curiosity"] == 85
    assert converted["label_status"] == "human_reviewed_blind"


def test_incomplete_review_is_rejected() -> None:
    row = {"review_set": "train", "review_status": "pending", "utterance": "Hello"}

    try:
        convert_row(row, {"utterance": "Hello"}, 1, "human_blind_review")
    except ReviewError as exc:
        assert "review_status" in str(exc)
    else:
        raise AssertionError("expected ReviewError")


# --- batch schema round trip -------------------------------------------------

_CANDIDATES = [
    {"utterance": "Do you like living alone?", "source": "nict_jle_real", "source_group": "int-1"},
    {"utterance": "That was really funny actually.", "source": "ami_real", "source_group": "ES1"},
    {"utterance": "Send it to my mobile please.", "source": "taskmaster1_woz_user_real", "source_group": "tm-9"},
]


def _fill_slot_csv(path: Path, scores: dict[str, dict[str, int]], reviewer_id: str) -> None:
    rows = list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))
    fieldnames = list(rows[0].keys())
    for row in rows:
        for axis, value in scores[row["item_id"]].items():
            row[f"reviewed_{axis}"] = str(value)
        row["reviewer_id"] = reviewer_id
        row["review_status"] = "completed"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_batch_export_import_aggregate_round_trip(tmp_path: Path) -> None:
    manifest = build_manifest(
        _CANDIDATES,
        annotation_batch="pilot",
        dataset_partition="train",
        axes="energy-humor",
        slots=["A", "B"],
        seed=7,
    )
    output = tmp_path / "pilot.csv"
    written = write_batch_csvs(manifest, output)
    slot_paths = [p for p in written if p.suffix == ".csv"]
    assert {p.name for p in slot_paths} == {"pilot.slotA.csv", "pilot.slotB.csv"}

    # slots get independently shuffled order
    assert manifest["slot_order"]["A"] != manifest["slot_order"]["B"]

    scores_a = {
        "pilot-0001": {"Energy": 40, "Humor": 5},
        "pilot-0002": {"Energy": 70, "Humor": 60},
        "pilot-0003": {"Energy": 50, "Humor": 10},
    }
    scores_b = {
        "pilot-0001": {"Energy": 44, "Humor": 5},
        "pilot-0002": {"Energy": 90, "Humor": 62},  # large Energy spread
        "pilot-0003": {"Energy": 52, "Humor": 12},
    }
    _fill_slot_csv(tmp_path / "pilot.slotA.csv", scores_a, "chanhee")
    _fill_slot_csv(tmp_path / "pilot.slotB.csv", scores_b, "minju")

    raw = load_batch_reviews(
        [tmp_path / "pilot.slotA.csv", tmp_path / "pilot.slotB.csv"],
        manifest,
        _CANDIDATES,
        "test",
    )
    assert len(raw) == 6  # 3 items x 2 slots
    assert all(r["label_status"] == "human_reviewed_blind_raw" for r in raw)
    assert all(r["label_source"]["Energy"] == "human" for r in raw)

    agg, report = aggregate(raw, adjudication={}, disagreement_threshold=15.0)
    assert len(agg) == 3
    item2 = next(r for r in agg if r["item_id"] == "pilot-0002")
    assert item2["axes"]["Energy"] == pytest.approx(80.0)  # mean(70, 90)
    assert report["flagged_count"] == 1
    assert report["flagged"][0]["item_id"] == "pilot-0002"


def test_batch_import_accepts_a_subset_of_slots(tmp_path: Path) -> None:
    manifest = build_manifest(
        _CANDIDATES, annotation_batch="calibration", dataset_partition="dev",
        axes="all", slots=["A", "B", "C", "D"], seed=5,
    )
    write_batch_csvs(manifest, tmp_path / "cal.csv")
    scores = {iid: {a: 50 for a in ("Formality", "Energy", "Intimacy", "Humor", "Curiosity")}
              for iid in ("calibration-0001", "calibration-0002", "calibration-0003")}
    _fill_slot_csv(tmp_path / "cal.slotA.csv", scores, "r1")
    _fill_slot_csv(tmp_path / "cal.slotC.csv", scores, "r3")

    raw = load_batch_reviews(
        [tmp_path / "cal.slotA.csv", tmp_path / "cal.slotC.csv"], manifest, _CANDIDATES, "test",
    )
    assert {r["reviewer_slot"] for r in raw} == {"A", "C"}
    assert len(raw) == 6  # 3 items x 2 supplied slots, D and B not required yet


def test_batch_import_still_requires_all_items_within_a_supplied_slot(tmp_path: Path) -> None:
    manifest = build_manifest(
        _CANDIDATES, annotation_batch="calibration", dataset_partition="dev",
        axes="all", slots=["A", "B"], seed=5,
    )
    write_batch_csvs(manifest, tmp_path / "cal.csv")
    rows = list(csv.DictReader((tmp_path / "cal.slotA.csv").open("r", encoding="utf-8-sig")))
    fieldnames = list(rows[0].keys())
    rows = rows[:2]  # drop one item
    for row in rows:
        for axis in ("Formality", "Energy", "Intimacy", "Humor", "Curiosity"):
            row[f"reviewed_{axis}"] = "50"
        row["reviewer_id"] = "r1"
        row["review_status"] = "completed"
    with (tmp_path / "cal.slotA.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ReviewError, match="missing"):
        load_batch_reviews([tmp_path / "cal.slotA.csv"], manifest, _CANDIDATES, "test")


def test_batch_import_rejects_duplicate_pk(tmp_path: Path) -> None:
    manifest = build_manifest(
        _CANDIDATES, annotation_batch="calibration", dataset_partition="train",
        axes="energy-curiosity-intimacy", slots=["A"], seed=1,
    )
    write_batch_csvs(manifest, tmp_path / "cal.csv")
    scores = {iid: {"Energy": 50, "Curiosity": 50, "Intimacy": 50} for iid in
              ("calibration-0001", "calibration-0002", "calibration-0003")}
    _fill_slot_csv(tmp_path / "cal.slotA.csv", scores, "rev1")
    # duplicate the whole slot file as a second --input for the same slot
    with pytest.raises(ReviewError, match="duplicate"):
        load_batch_reviews(
            [tmp_path / "cal.slotA.csv", tmp_path / "cal.slotA.csv"],
            manifest, _CANDIDATES, "test",
        )


def test_batch_adjudication_overrides_but_keeps_raw(tmp_path: Path) -> None:
    manifest = build_manifest(
        _CANDIDATES, annotation_batch="first40", dataset_partition="train",
        axes="energy-curiosity-intimacy", slots=["A", "B"], seed=3,
    )
    write_batch_csvs(manifest, tmp_path / "f40.csv")
    a = {iid: {"Energy": 20, "Curiosity": 20, "Intimacy": 20} for iid in
         ("first40-0001", "first40-0002", "first40-0003")}
    b = {iid: {"Energy": 80, "Curiosity": 80, "Intimacy": 80} for iid in
         ("first40-0001", "first40-0002", "first40-0003")}
    _fill_slot_csv(tmp_path / "f40.slotA.csv", a, "r1")
    _fill_slot_csv(tmp_path / "f40.slotB.csv", b, "r2")
    raw = load_batch_reviews([tmp_path / "f40.slotA.csv", tmp_path / "f40.slotB.csv"], manifest, _CANDIDATES, "test")
    adj = {"first40-0001": {"Energy": 35, "note": "third reviewer call"}}
    agg, _ = aggregate(raw, adjudication=adj, disagreement_threshold=15.0)
    resolved = next(r for r in agg if r["item_id"] == "first40-0001")
    assert resolved["axes"]["Energy"] == pytest.approx(35.0)
    assert resolved["label_source"]["Energy"] == "human_adjudicated"
    assert resolved["raw_scores"]["A"]["Energy"] == 20.0
    assert resolved["raw_scores"]["B"]["Energy"] == 80.0
