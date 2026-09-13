# -*- coding: utf-8 -*-
"""
Week 2 ML baseline checks.

Run from the repository root:
  python tests/test_ai_week2_ml_baseline.py
"""

import os
import sys
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

from ai.analyzers import MLAxisAnalyzer, get_axis_analyzer
from ai.contracts import AXIS_KEYS
from ai.evaluate_axis_analyzers import split_by_source_group
from ai.ml_baseline import (
    AxisTrainingExample,
    TfidfKnnAxisRegressor,
    _load_jsonl_axis_dataset,
    _validate_partial_axes,
    load_default_axis_dataset,
)
from pathlib import Path


def test_ml_axis_analyzer_returns_existing_contract() -> None:
    analyzer = MLAxisAnalyzer()
    result = analyzer.analyze("Could you explain why this phrase sounds casual?").to_axes_dict()
    assert tuple(result.keys()) == AXIS_KEYS
    assert all(0 <= value <= 100 for value in result.values())


def test_ml_baseline_uses_training_neighbors() -> None:
    examples = load_default_axis_dataset()
    model = TfidfKnnAxisRegressor(k=3).fit(examples)
    prediction = model.predict("no cap that was lowkey hilarious")
    assert prediction["Formality"] < 50
    assert prediction["Humor"] >= 20


def test_ml_baseline_can_include_word_bigrams() -> None:
    examples = load_default_axis_dataset()
    model = TfidfKnnAxisRegressor(k=3, word_ngram_max=2).fit(examples)

    prediction = model.predict("could you explain this phrase")

    assert set(prediction) == set(AXIS_KEYS)
    assert all(0 <= value <= 100 for value in prediction.values())


def test_source_group_holdout_keeps_each_group_on_one_side() -> None:
    label = {axis: 50 for axis in AXIS_KEYS}
    holdout_group = next(
        f"meeting-{index}"
        for index in range(100)
        if int.from_bytes(hashlib.sha256(f"meeting-{index}".encode("utf-8")).digest()[:4], "big") % 10 == 0
    )
    examples = [
        AxisTrainingExample("First meeting turn", label, "conversation", source="ami", source_group="meeting-1"),
        AxisTrainingExample("Second meeting turn", label, "conversation", source="ami", source_group="meeting-1"),
        AxisTrainingExample("Independent turn", label, "conversation", source="ami", source_group=holdout_group),
    ]

    train, test = split_by_source_group(examples)
    training_groups = {example.source_group for example in train}
    test_groups = {example.source_group for example in test}

    assert training_groups.isdisjoint(test_groups)


def test_analyzer_factory_can_select_ml() -> None:
    analyzer = get_axis_analyzer("ml")
    result = analyzer.analyze("Please explain this sentence.").to_axes_dict()
    assert set(result) == set(AXIS_KEYS)


def test_ml_dataset_can_be_selected_by_env(monkeypatch) -> None:
    dataset_path = os.path.join(ROOT, "tests", ".tmp_axis_dataset.jsonl")
    try:
        with open(dataset_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"utterance":"Could you help me?","axes":{"Formality":55,"Energy":30,"Intimacy":35,"Humor":5,"Curiosity":80},"style":"learner_request"}\n'
            )
        monkeypatch.setenv("PALLY_AXIS_DATASET", dataset_path)

        examples = load_default_axis_dataset()
        assert len(examples) == 1
        assert examples[0].utterance == "Could you help me?"
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


def test_ml_dataset_relative_env_path_is_resolved_from_repo_root(monkeypatch) -> None:
    dataset_path = os.path.join(ROOT, "tests", ".tmp_relative_axis_dataset.jsonl")
    try:
        with open(dataset_path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"utterance":"Please repeat that.","axes":{"Formality":55,"Energy":30,"Intimacy":35,"Humor":5,"Curiosity":80},"style":"learner_request"}\n'
            )
        monkeypatch.setenv("PALLY_AXIS_DATASET", "tests/.tmp_relative_axis_dataset.jsonl")

        examples = load_default_axis_dataset()
        assert len(examples) == 1
        assert examples[0].utterance == "Please repeat that."
    finally:
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


def _full_label(**overrides: int) -> dict[str, int]:
    label = {axis: 50 for axis in AXIS_KEYS}
    label.update(overrides)
    return label


def test_validate_partial_axes_keeps_subset_and_rejects_bad_values() -> None:
    assert _validate_partial_axes({"Energy": 70, "Curiosity": 20}) == {"Energy": 70, "Curiosity": 20}
    with pytest.raises(ValueError):
        _validate_partial_axes({"Energy": 150})
    with pytest.raises(ValueError):
        _validate_partial_axes({"Energy": float("nan")})
    with pytest.raises(ValueError):
        _validate_partial_axes({}, min_axes=1)


def test_load_partial_dataset_retains_label_source(tmp_path: Path) -> None:
    dataset_path = tmp_path / "partial.jsonl"
    dataset_path.write_text(
        '{"utterance":"wow really","axes":{"Energy":80},"label_source":{"Energy":"human"}}\n',
        encoding="utf-8",
    )
    examples = _load_jsonl_axis_dataset(dataset_path, allow_partial=True)
    assert examples[0].label == {"Energy": 80}
    assert examples[0].label_source == {"Energy": "human"}


def test_fit_require_full_axes_rejects_partial_rows() -> None:
    partial = AxisTrainingExample("only energy", {"Energy": 60}, "conversation")
    with pytest.raises(ValueError):
        TfidfKnnAxisRegressor().fit([partial], require_full_axes=True)


def test_predict_partial_returns_none_for_unlabeled_axis() -> None:
    examples = [
        AxisTrainingExample("great question about the plan", {"Energy": 70, "Curiosity": 80}, "conversation"),
        AxisTrainingExample("tell me more about the plan", {"Energy": 40, "Curiosity": 75}, "conversation"),
    ]
    model = TfidfKnnAxisRegressor(k=2).fit(examples)
    prediction = model.predict_partial("what about the plan")
    assert prediction["Energy"] is not None
    assert prediction["Curiosity"] is not None
    assert prediction["Humor"] is None  # no training example carries Humor


def test_predict_partial_filters_valid_neighbors_from_full_ranking() -> None:
    # The nearest neighbor lacks Humor; predict_partial must skip it and still
    # produce a Humor value from the next-best neighbor that has one.
    examples = [
        AxisTrainingExample("the quick brown fox jumps", {"Energy": 90}, "conversation"),
        AxisTrainingExample("the quick brown fox naps", {"Energy": 20, "Humor": 65}, "conversation"),
    ]
    model = TfidfKnnAxisRegressor(k=1).fit(examples)
    prediction = model.predict_partial("the quick brown fox")
    assert prediction["Humor"] == pytest.approx(65.0)


def run() -> None:
    test_ml_axis_analyzer_returns_existing_contract()
    test_ml_baseline_uses_training_neighbors()
    test_analyzer_factory_can_select_ml()
    print("Week 2 ML baseline checks passed.")


if __name__ == "__main__":
    run()
