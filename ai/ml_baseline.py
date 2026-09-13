# -*- coding: utf-8 -*-
"""
Dependency-free ML baseline for Pally's five-axis scoring.

This is intentionally small: it gives us a measurable ML candidate without
adding deployment dependencies. The model uses TF-IDF vectors and weighted
nearest-neighbor regression over the labeled utterance dataset.
"""

import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.contracts import AXIS_KEYS
from data.dataset import DATASET

TOKEN_PATTERN = re.compile(r"[a-z']+|[!?]+")
WEEK2_DATASET_PATH = Path(ROOT) / "data" / "axis_dataset_week2.jsonl"
AXIS_DATASET_ENV = "PALLY_AXIS_DATASET"


@dataclass(frozen=True)
class AxisTrainingExample:
    utterance: str
    label: dict[str, int]
    style: str
    source: str = ""
    source_group: str = ""
    # axis -> provenance of that axis label ("human", "ai_draft", "seed", ...).
    # Empty for legacy rows. Only populated when a dataset is loaded with
    # allow_partial=True, where a row may carry a subset of the five axes.
    label_source: dict[str, str] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _feature_tokens(text: str, word_ngram_max: int) -> list[str]:
    tokens = _tokenize(text)
    if word_ngram_max == 1:
        return tokens
    features = list(tokens)
    for size in range(2, word_ngram_max + 1):
        features.extend(f"__ng{size}__:{'|'.join(tokens[index : index + size])}" for index in range(len(tokens) - size + 1))
    return features


def _validate_axes(raw_axes: dict[str, Any]) -> dict[str, int]:
    axes = {key: int(raw_axes[key]) for key in AXIS_KEYS}
    for axis, value in axes.items():
        if value < 0 or value > 100:
            raise ValueError(f"{axis} score must be between 0 and 100")
    return axes


def _validate_partial_axes(raw_axes: dict[str, Any], min_axes: int = 1) -> dict[str, int]:
    """Validate a label that may cover only a subset of the five axes.

    A missing axis is allowed and simply omitted from the result. A present
    axis must be a finite number in ``[0, 100]``; a NaN/inf or out-of-range
    value is a hard error rather than being silently dropped or clamped, so a
    malformed partial label never enters the training set unnoticed.
    """
    axes: dict[str, int] = {}
    for key in AXIS_KEYS:
        if key not in raw_axes or raw_axes[key] is None:
            continue
        value = float(raw_axes[key])
        if not math.isfinite(value):
            raise ValueError(f"{key} score must be finite, got {raw_axes[key]!r}")
        if value < 0 or value > 100:
            raise ValueError(f"{key} score must be between 0 and 100, got {value}")
        axes[key] = int(value)
    if len(axes) < min_axes:
        raise ValueError(f"partial label needs at least {min_axes} axis score(s), got {sorted(axes)}")
    return axes


def _load_jsonl_axis_dataset(path: Path, *, allow_partial: bool = False) -> list[AxisTrainingExample]:
    """Load a JSONL axis dataset.

    With ``allow_partial=False`` (default, deployment path) every row must
    carry all five axes. With ``allow_partial=True`` a row may carry a subset
    of the axes; the per-axis provenance from an optional ``label_source``
    object is retained so a caller can tell a human label from an AI draft.
    """
    examples: list[AxisTrainingExample] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            item = json.loads(stripped)
            if allow_partial:
                label = _validate_partial_axes(item["axes"])
                raw_source = item.get("label_source") or {}
                label_source = {axis: str(raw_source[axis]) for axis in label if axis in raw_source}
            else:
                label = _validate_axes(item["axes"])
                label_source = {}
            examples.append(
                AxisTrainingExample(
                    utterance=str(item["utterance"]),
                    label=label,
                    style=str(item.get("style", "conversation")),
                    source=str(item.get("source", "")),
                    source_group=str(item.get("source_group", "")),
                    label_source=label_source,
                )
            )
    if not examples:
        raise ValueError(f"no examples found in {path}")
    return examples


def _load_legacy_axis_dataset() -> list[AxisTrainingExample]:
    return [
        AxisTrainingExample(
            utterance=item["utterance"],
            label=_validate_axes(item["label"]),
            style=item["style"],
            source="legacy",
            source_group="",
        )
        for item in DATASET
    ]


def load_default_axis_dataset() -> list[AxisTrainingExample]:
    """Load the active ML dataset, preferring the conversation-first Week 2 JSONL."""
    configured_path = os.getenv(AXIS_DATASET_ENV)
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = Path(ROOT) / path
        return _load_jsonl_axis_dataset(path)
    if WEEK2_DATASET_PATH.exists():
        return _load_jsonl_axis_dataset(WEEK2_DATASET_PATH)
    return _load_legacy_axis_dataset()


class TfidfKnnAxisRegressor:
    def __init__(self, k: int = 5, word_ngram_max: int = 1) -> None:
        if k <= 0:
            raise ValueError("k must be positive")
        if word_ngram_max < 1:
            raise ValueError("word_ngram_max must be at least one")
        self.k = k
        self.word_ngram_max = word_ngram_max
        self.examples: list[AxisTrainingExample] = []
        self.idf: dict[str, float] = {}
        self.vectors: list[dict[str, float]] = []

    def fit(
        self,
        examples: list[AxisTrainingExample],
        *,
        require_full_axes: bool = False,
    ) -> "TfidfKnnAxisRegressor":
        if not examples:
            raise ValueError("at least one training example is required")
        if require_full_axes:
            # Deployment adapter path: predict() indexes label[axis] directly,
            # so a partial row here would surface as a KeyError mid-turn. Fail
            # loudly at fit time instead.
            incomplete = [
                index
                for index, example in enumerate(examples)
                if any(axis not in example.label for axis in AXIS_KEYS)
            ]
            if incomplete:
                raise ValueError(
                    f"require_full_axes=True but {len(incomplete)} example(s) miss an axis "
                    f"(first at index {incomplete[0]}); use predict_partial for subset labels"
                )
        self.examples = examples
        doc_count = len(examples)
        document_frequency: Counter[str] = Counter()
        for example in examples:
            document_frequency.update(set(_feature_tokens(example.utterance, self.word_ngram_max)))
        self.idf = {
            token: math.log((doc_count + 1) / (count + 1)) + 1.0
            for token, count in document_frequency.items()
        }
        self.vectors = [self._vectorize(example.utterance) for example in examples]
        return self

    def predict(self, utterance: str) -> dict[str, int]:
        if not self.examples:
            raise RuntimeError("model is not fitted")
        query = self._vectorize(utterance)
        similarities = [
            (self._cosine(query, vector), index)
            for index, vector in enumerate(self.vectors)
        ]
        similarities.sort(reverse=True)
        neighbors = similarities[: min(self.k, len(similarities))]

        weights = [(similarity if similarity > 0 else 0.001, index) for similarity, index in neighbors]
        total_weight = sum(weight for weight, _ in weights)
        prediction: dict[str, int] = {}
        for axis in AXIS_KEYS:
            value = sum(weight * self.examples[index].label[axis] for weight, index in weights) / total_weight
            prediction[axis] = max(0, min(100, round(value)))
        return prediction

    def predict_partial(self, utterance: str) -> dict[str, float | None]:
        """Research-only per-axis prediction that tolerates subset labels.

        For each axis the full similarity ranking is computed once, then the
        first ``k`` neighbors that actually carry that axis are averaged with
        similarity weights. Returns ``None`` for an axis when no training
        example carries it (distinct from a degenerate all-similarity-zero
        neighborhood, which still yields a number via the 0.001 weight floor,
        matching ``predict``).

        The result may contain ``None`` and non-integer values, so it does not
        satisfy the ``AxisResult`` contract and must not be fed to the
        deployment analyzers directly.
        """
        if not self.examples:
            raise RuntimeError("model is not fitted")
        query = self._vectorize(utterance)
        similarities = sorted(
            ((self._cosine(query, vector), index) for index, vector in enumerate(self.vectors)),
            reverse=True,
        )
        prediction: dict[str, float | None] = {}
        for axis in AXIS_KEYS:
            picked: list[tuple[float, int]] = []
            for similarity, index in similarities:
                if axis in self.examples[index].label:
                    picked.append((similarity, index))
                    if len(picked) >= self.k:
                        break
            if not picked:
                prediction[axis] = None
                continue
            weights = [(similarity if similarity > 0 else 0.001, index) for similarity, index in picked]
            total_weight = sum(weight for weight, _ in weights)
            value = sum(weight * self.examples[index].label[axis] for weight, index in weights) / total_weight
            prediction[axis] = max(0.0, min(100.0, value))
        return prediction

    def _vectorize(self, utterance: str) -> dict[str, float]:
        counts = Counter(_feature_tokens(utterance, self.word_ngram_max))
        if not counts:
            return {}
        max_count = max(counts.values())
        return {
            token: (count / max_count) * self.idf.get(token, 1.0)
            for token, count in counts.items()
        }

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(value * right.get(token, 0.0) for token, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
