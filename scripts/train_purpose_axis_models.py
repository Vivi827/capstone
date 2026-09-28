# -*- coding: utf-8 -*-
"""Train the purpose classifier and common axis regressor (PM final design Sec. 10.2).

Purpose classifier: word TF-IDF(1-2gram) + char TF-IDF(3-5gram) -> LogisticRegression
  (class_weight=balanced, C=1.0, max_iter=2000)
Axis regressor: same TF-IDF features -> 3x Ridge(alpha=1.0), one per axis
  (Formality/Humor/Curiosity), output clipped to [0,100] and rounded to nearest 5.

Both fit ONLY on split=="train" rows (Sec. 10.3 leak prevention). The axis
regressor never sees purpose as a feature -- conditions A and B share its output.

Requires human labels (purpose_primary, formality/humor/curiosity) filled in by
the 4-researcher labeling pass; run against data/fixtures/pally_purpose_v1_items_100.jsonl
once that's done. Until then, pass --items pointing at a synthetic fixture to
smoke-test the pipeline -- those runs verify the CODE, not any real result.

Usage:
  python scripts/train_purpose_axis_models.py --items data/fixtures/pally_purpose_v1_items_100.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge

AXES = ("formality", "humor", "curiosity")


def load_train_rows(items_path: Path) -> list[dict]:
    rows = [json.loads(line) for line in items_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    train_rows = [r for r in rows if r.get("split") == "train"]
    missing_purpose = [r["item_id"] for r in train_rows if not r.get("purpose_primary")]
    missing_axes = [r["item_id"] for r in train_rows if any(r.get(a) is None for a in AXES)]
    if missing_purpose or missing_axes:
        raise ValueError(
            f"{len(missing_purpose)} train rows missing purpose_primary, "
            f"{len(missing_axes)} missing an axis score -- labeling isn't done yet. "
            "Use a synthetic fixture to test the code, not this file, until it is."
        )
    return train_rows


def build_features(texts: list[str]) -> tuple[TfidfVectorizer, TfidfVectorizer]:
    word_vec = TfidfVectorizer(ngram_range=(1, 2), analyzer="word")
    char_vec = TfidfVectorizer(ngram_range=(3, 5), analyzer="char")
    word_vec.fit(texts)
    char_vec.fit(texts)
    return word_vec, char_vec


def vectorize(word_vec: TfidfVectorizer, char_vec: TfidfVectorizer, texts: list[str]):
    return hstack([word_vec.transform(texts), char_vec.transform(texts)])


def train(items_path: Path, out_dir: Path) -> dict:
    rows = load_train_rows(items_path)
    texts = [r["target_turn"] for r in rows]

    word_vec, char_vec = build_features(texts)
    X = vectorize(word_vec, char_vec, texts)

    purpose_clf = LogisticRegression(class_weight="balanced", C=1.0, max_iter=2000)
    purpose_clf.fit(X, [r["purpose_primary"] for r in rows])

    axis_models = {}
    for axis in AXES:
        y = np.array([r[axis] for r in rows], dtype=float)
        model = Ridge(alpha=1.0)
        model.fit(X, y)
        axis_models[axis] = model

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"word_vec": word_vec, "char_vec": char_vec, "purpose_clf": purpose_clf, "axis_models": axis_models},
        out_dir / "purpose_axis_models.joblib",
    )
    return {"n_train": len(rows), "purpose_classes": sorted(purpose_clf.classes_.tolist())}


def predict(bundle_path: Path, texts: list[str]) -> list[dict]:
    bundle = joblib.load(bundle_path)
    X = vectorize(bundle["word_vec"], bundle["char_vec"], texts)
    purpose_pred = bundle["purpose_clf"].predict(X)
    results = []
    for i, text in enumerate(texts):
        axes = {}
        for axis, model in bundle["axis_models"].items():
            raw = float(model.predict(X[i])[0])
            clipped = max(0.0, min(100.0, raw))
            axes[axis] = round(clipped / 5) * 5
        results.append({"target_turn": text, "predicted_purpose": purpose_pred[i], "predicted_axes": axes})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, default=Path("data/fixtures/pally_purpose_v1_items_100.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/models"))
    args = parser.parse_args()

    summary = train(args.items, args.out_dir)
    print(f"trained on {summary['n_train']} items, purpose classes: {summary['purpose_classes']}")
    print(f"saved to {args.out_dir / 'purpose_axis_models.joblib'}")


if __name__ == "__main__":
    main()
