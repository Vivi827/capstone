# -*- coding: utf-8 -*-
"""Unit tests for the dependency-free ridge axis regressor (cycle 4c self-check)."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.contracts import AXIS_KEYS
from ai.linear_axis_model import LinearAxisExample, RidgeAxisRegressor


def _label(**overrides: float) -> dict[str, float]:
    label = {axis: 50.0 for axis in AXIS_KEYS}
    label.update(overrides)
    return label


def test_ridge_recovers_a_clean_linear_signal() -> None:
    """A single strongly-predictive token should drive its axis toward the
    label it was trained with, and the model should not collapse to the
    mean-only bias term."""
    examples = []
    for i in range(30):
        examples.append(LinearAxisExample(f"please help me {i}", _label(Formality=95.0)))
        examples.append(LinearAxisExample(f"whatever man {i}", _label(Formality=5.0)))
    model = RidgeAxisRegressor(word_ngram_max=1, min_df=1, epochs=60, lr=0.8).fit(examples)

    polite = model.predict_float("please help me")
    casual = model.predict_float("whatever man")
    assert polite["Formality"] > 70
    assert casual["Formality"] < 30
    # a token that never appeared should fall back toward the learned bias,
    # not an arbitrary extreme
    neutral = model.predict_float("completely unseen sentence")
    assert 20 < neutral["Formality"] < 80


def test_ridge_predictions_stay_in_bounds() -> None:
    examples = [
        LinearAxisExample("could you please explain that again", _label(Formality=90.0, Curiosity=85.0)),
        LinearAxisExample("hey what's up", _label(Formality=10.0, Intimacy=70.0)),
        LinearAxisExample("that is hilarious honestly", _label(Humor=90.0, Energy=70.0)),
    ] * 5
    model = RidgeAxisRegressor(word_ngram_max=1, min_df=1, epochs=30).fit(examples)
    for text in ("could you please explain that again", "hey what's up", "a totally novel sentence"):
        pred = model.predict(text)
        assert set(pred) == set(AXIS_KEYS)
        for axis, value in pred.items():
            assert isinstance(value, int)
            assert 0 <= value <= 100


def test_ridge_handles_partial_labels_per_axis() -> None:
    """An example missing some axes must not break fitting or bleed into
    other examples' axes."""
    examples = [
        LinearAxisExample("energetic one", {"Energy": 90.0}),
        LinearAxisExample("calm one", {"Energy": 10.0}),
        LinearAxisExample("formal one", {"Formality": 90.0}),
        LinearAxisExample("casual one", {"Formality": 10.0}),
    ]
    model = RidgeAxisRegressor(word_ngram_max=1, min_df=1, epochs=30).fit(examples)
    pred = model.predict("energetic one")
    assert set(pred) == set(AXIS_KEYS)  # every axis still predicted (falls back to bias where unlabeled)


def test_ridge_is_deterministic_given_a_seed() -> None:
    examples = [
        LinearAxisExample("please help me", _label(Formality=90.0)),
        LinearAxisExample("whatever man", _label(Formality=10.0)),
    ] * 10
    a = RidgeAxisRegressor(word_ngram_max=1, min_df=1, epochs=20, seed=42).fit(examples)
    b = RidgeAxisRegressor(word_ngram_max=1, min_df=1, epochs=20, seed=42).fit(examples)
    assert a.predict("please help me") == b.predict("please help me")
