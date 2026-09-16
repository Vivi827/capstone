# -*- coding: utf-8 -*-
"""Dependency-free linear (ridge) axis regressor.

A more expressive student than the TF-IDF k-NN: it learns a global weight per
feature per axis (e.g. "please -> +Formality") instead of copying nearby
training rows. Same feature pipeline as `ml_baseline` (word n-gram TF-IDF,
L2-normalized rows), trained with mini-batch SGD so no numpy is needed.

Pure Python, so a winning candidate ships without new runtime dependencies.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

from ai.contracts import AXIS_KEYS
from ai.ml_baseline import _feature_tokens


@dataclass(frozen=True)
class LinearAxisExample:
    utterance: str
    label: dict[str, float]  # 0-100 per axis; may be partial
    source: str = ""


class RidgeAxisRegressor:
    def __init__(
        self,
        word_ngram_max: int = 1,
        min_df: int = 2,
        max_features: int = 4000,
        l2: float = 1.0,
        lr: float = 0.5,
        epochs: int = 40,
        batch_size: int = 32,
        seed: int = 20260911,
    ) -> None:
        self.word_ngram_max = word_ngram_max
        self.min_df = min_df
        self.max_features = max_features
        self.l2 = l2
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.idf: dict[str, float] = {}
        self.vocab: dict[str, int] = {}
        self.weights: dict[str, list[float]] = {}
        self.bias: dict[str, float] = {}

    # --- features -----------------------------------------------------------

    def _fit_vocab(self, utterances: list[str]) -> None:
        df: Counter[str] = Counter()
        for text in utterances:
            df.update(set(_feature_tokens(text, self.word_ngram_max)))
        doc_count = len(utterances)
        kept = [tok for tok, c in df.items() if c >= self.min_df]
        kept.sort(key=lambda t: (-df[t], t))
        kept = kept[: self.max_features]
        self.vocab = {tok: i for i, tok in enumerate(kept)}
        self.idf = {
            tok: math.log((doc_count + 1) / (df[tok] + 1)) + 1.0 for tok in kept
        }

    def _vectorize(self, text: str) -> dict[int, float]:
        counts = Counter(_feature_tokens(text, self.word_ngram_max))
        if not counts:
            return {}
        max_count = max(counts.values())
        vec: dict[int, float] = {}
        for tok, c in counts.items():
            j = self.vocab.get(tok)
            if j is None:
                continue
            vec[j] = (c / max_count) * self.idf[tok]
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            for j in vec:
                vec[j] /= norm
        return vec

    # --- training ----------------------------------------------------------

    def fit(self, examples: list[LinearAxisExample]) -> "RidgeAxisRegressor":
        if not examples:
            raise ValueError("need at least one example")
        self._fit_vocab([e.utterance for e in examples])
        vectors = [self._vectorize(e.utterance) for e in examples]
        n_feat = len(self.vocab)
        rng = random.Random(self.seed)

        for axis in AXIS_KEYS:
            idx = [i for i, e in enumerate(examples) if axis in e.label]
            if len(idx) < 10:
                self.weights[axis] = [0.0] * n_feat
                self.bias[axis] = (
                    sum(examples[i].label[axis] for i in idx) / len(idx) / 100.0 if idx else 0.5
                )
                continue
            targets = {i: examples[i].label[axis] / 100.0 for i in idx}
            w = [0.0] * n_feat
            b = sum(targets.values()) / len(targets)
            order = list(idx)
            n_train = len(order)
            for _ in range(self.epochs):
                rng.shuffle(order)
                for start in range(0, len(order), self.batch_size):
                    batch = order[start : start + self.batch_size]
                    gw: dict[int, float] = {}
                    gb = 0.0
                    for i in batch:
                        vec = vectors[i]
                        pred = b + sum(w[j] * val for j, val in vec.items())
                        err = pred - targets[i]
                        gb += err
                        for j, val in vec.items():
                            gw[j] = gw.get(j, 0.0) + err * val
                    scale = self.lr / len(batch)
                    b -= scale * gb
                    # Standard ridge SGD: the L2 penalty (l2/2 * ||w||^2 over the
                    # full training set) applies to EVERY weight every step, not
                    # only the features active in this batch -- otherwise rare
                    # features are shrunk far less than frequent ones per step.
                    l2_scale = self.lr * self.l2 / n_train
                    for j in range(n_feat):
                        w[j] -= l2_scale * w[j]
                    for j, g in gw.items():
                        w[j] -= scale * g
            self.weights[axis] = w
            self.bias[axis] = b
        return self

    def predict(self, utterance: str) -> dict[str, int]:
        vec = self._vectorize(utterance)
        out: dict[str, int] = {}
        for axis in AXIS_KEYS:
            w = self.weights.get(axis)
            if w is None:
                out[axis] = 50
                continue
            score = self.bias[axis] + sum(w[j] * val for j, val in vec.items())
            out[axis] = max(0, min(100, round(score * 100)))
        return out

    def predict_float(self, utterance: str) -> dict[str, float]:
        vec = self._vectorize(utterance)
        out: dict[str, float] = {}
        for axis in AXIS_KEYS:
            w = self.weights.get(axis)
            if w is None:
                out[axis] = 50.0
                continue
            score = self.bias[axis] + sum(w[j] * val for j, val in vec.items())
            out[axis] = max(0.0, min(100.0, score * 100))
        return out
