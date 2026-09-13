# -*- coding: utf-8 -*-
"""Phase 2 candidate builders: quota and determinism."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import json
from pathlib import Path

from scripts.build_calibration_pilot_sets import build_sets, canonical_group
from scripts.build_train_first40_set import REASON_QUOTA, load_jsonl, select_first40

FIX = Path(ROOT) / "data" / "fixtures"


def test_first40_hits_the_fixed_reason_quota_and_is_deterministic() -> None:
    rows = load_jsonl(FIX / "ml_transition_train_active_ec_candidates_120.jsonl")
    selected_a, extra_a = select_first40(rows, seed=20260910)
    selected_b, _ = select_first40(rows, seed=20260910)

    assert len(selected_a) == sum(REASON_QUOTA.values()) == 40
    assert [r["utterance"] for r in selected_a] == [r["utterance"] for r in selected_b]
    assert len(extra_a["remainder"]) == len(rows) - 40

    from collections import Counter

    per_reason = Counter(r["selection_reason"] for r in selected_a)
    assert dict(per_reason) == REASON_QUOTA


def test_calibration_pilot_disjoint_and_reserved_safe() -> None:
    reservoir = load_jsonl(FIX / "ml_transition_train_candidates_1200.jsonl")
    ec120 = {canonical_group(r) for r in load_jsonl(FIX / "ml_transition_train_active_ec_candidates_120.jsonl")}
    reserved = {
        r.get("canonical_group") or canonical_group(r)
        for r in load_jsonl(FIX / "ml_transition_reserved_final_test_pool.jsonl")
    }

    calib, pilot, manifest = build_sets(reservoir, ec120, reserved, seed=20260910)

    assert len(calib) == 90
    assert manifest["calibration"]["per_source"] == {
        "ami_real": 30,
        "nict_jle_real": 30,
        "taskmaster1_woz_user_real": 30,
    }
    assert manifest["pilot"]["disagree"] == {"Energy": 8, "Humor": 8}

    calib_groups = {canonical_group(r) for r in calib}
    pilot_groups = {canonical_group(r) for r in pilot}
    assert calib_groups.isdisjoint(pilot_groups)
    assert (calib_groups | pilot_groups).isdisjoint(reserved)
    assert (calib_groups | pilot_groups).isdisjoint(ec120)
    # one distinct group per calibration item
    assert len(calib_groups) == 90

    # every pilot row carries an arm label; event + control arms are AMI-only
    assert {r["pilot_arm"] for r in pilot} == {"event", "ami_nonlaugh_control", "disagree", "residual"}
    for arm in ("event", "ami_nonlaugh_control"):
        assert all(r["source"] == "ami_real" for r in pilot if r["pilot_arm"] == arm)
    # calibration must not consume the laughter groups the event arm needs
    event_groups = {canonical_group(r) for r in pilot if r["pilot_arm"] == "event"}
    assert calib_groups.isdisjoint(event_groups)
