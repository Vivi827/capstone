# -*- coding: utf-8 -*-
"""Days 2-3 diagnosis E1: teacher fidelity vs student capacity.

Question: is ML weak on dev-200 because the supervision (weak labels) is the
ceiling, or because the kNN cannot even reproduce its own training signal?

Method, inside the dev-group-purged training set only:
  * group-held-out split (seeded hash on canonical group).
  * fit ML on the train part, predict the held-out part, measure agreement
    with the STORED weak labels (MAE / Spearman), overall and per source.
  * run `draft_axes` on the same held-out part, measure ITS agreement with
    the stored weak labels.

Reading:
  * student reproduces stored labels well (low MAE, high rho) but both are
    far from human on dev  ->  supervision is the ceiling; more of the same
    automated labels will not help.
  * student cannot reproduce the stored labels (rho << draft_axes-vs-stored)
    ->  the representation is the limit; fix representation before labels.

Caveat printed in the output: NICT stored labels are themselves
`codex_accept_draft`, so "reproduce the stored label" on NICT is close to
"reproduce draft_axes". AMI / Taskmaster / CHiME / HCRC stored labels are
`ai_draft_needs_human_review` (also draft_axes output). None of the stored
labels are independent human labels. This experiment measures internal
consistency, not correctness.

No human labels created. Reserved pool not opened. dev-200 not used here.

Run from the repository root:
  python scripts/diagnose_teacher_fidelity.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.contracts import AXIS_KEYS
from ai.ml_baseline import AxisTrainingExample, TfidfKnnAxisRegressor, _validate_axes
from scripts.draft_label_nict_jle_candidates import draft_axes
from scripts.reserve_ml_transition_final_pool import (
    canonical_group,
    recover_nict_training_groups,
    training_group_set,
)

TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"
NICT_RAW_PATH = Path(ROOT) / "data" / "fixtures" / "nict_jle_learner_utterances.jsonl"
GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"
HOLDOUT_SEED = "teacher-fidelity-20260911"
HOLDOUT_BUCKETS = 5  # ~1/5 of groups held out


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _rank(values: list[float]) -> list[float]:
    ordered = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        avg = (i + j + 2) / 2
        for _, oi in ordered[i : j + 1]:
            ranks[oi] = avg
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


def _spearman(e: list[float], p: list[float]) -> float:
    return _pearson(_rank(e), _rank(p))


def _row_group(row: dict[str, Any], nict_raw: list[dict[str, Any]]) -> str:
    if str(row.get("source", "")).startswith("nict"):
        sl = row.get("source_line")
        if sl is not None and 0 <= int(sl) - 1 < len(nict_raw):
            raw = nict_raw[int(sl) - 1]
            if str(raw["utterance"]).strip() == str(row["utterance"]).strip():
                return canonical_group(raw)
    return canonical_group(row)


def _held_out(group: str) -> bool:
    digest = hashlib.sha256(f"{HOLDOUT_SEED}|{group}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % HOLDOUT_BUCKETS == 0


def _as_example(row: dict[str, Any]) -> AxisTrainingExample | None:
    try:
        label = _validate_axes(row["axes"])
    except (KeyError, ValueError):
        return None
    return AxisTrainingExample(
        utterance=str(row["utterance"]),
        label=label,
        style=str(row.get("style", "conversation")),
        source=str(row.get("source", "")),
        source_group=str(row.get("source_group", "")),
    )


def _agreement(expected: list[dict[str, int]], predicted: list[dict[str, float]]) -> dict[str, Any]:
    per_mae: dict[str, float] = {}
    per_rho: dict[str, float] = {}
    for axis in AXIS_KEYS:
        e = [float(x[axis]) for x in expected]
        p = [float(x[axis]) for x in predicted]
        per_mae[axis] = sum(abs(pp - ee) for ee, pp in zip(e, p)) / len(e)
        per_rho[axis] = _spearman(e, p)
    valid = [v for v in per_rho.values() if not math.isnan(v)]
    na = [a for a, v in per_rho.items() if math.isnan(v)]
    return {
        "mae": sum(per_mae.values()) / len(per_mae),
        "rho": sum(valid) / len(valid) if valid else float("nan"),
        "na": na,
        "per_mae": per_mae,
        "per_rho": per_rho,
    }


def _fmt(a: dict[str, Any]) -> str:
    rho = "n/a" if math.isnan(a["rho"]) else f"{a['rho']:.3f}"
    na = f"  (na: {', '.join(a['na'])})" if a["na"] else ""
    return f"MAE {a['mae']:6.3f}   rho {rho:>6}{na}"


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    nict_raw = load_jsonl(NICT_RAW_PATH)
    gold = load_jsonl(GOLD_PATH)

    nict_groups, nict_stats = recover_nict_training_groups(train_rows, nict_raw)
    if nict_stats.get("verified") != nict_stats.get("nict_training_rows"):
        raise SystemExit(f"NICT provenance incomplete: {nict_stats}")
    dev_groups = {canonical_group(r) for r in gold}

    purged = [r for r in train_rows if _row_group(r, nict_raw) not in dev_groups]
    print(f"purged training rows: {len(purged)} / {len(train_rows)}")
    print(f"stored label_status mix: {dict(Counter(r.get('label_status') for r in purged))}")
    print(f"holdout: sha256('{HOLDOUT_SEED}|group') %% {HOLDOUT_BUCKETS} == 0\n")

    train_part: list[AxisTrainingExample] = []
    hold_rows: list[dict[str, Any]] = []
    for row in purged:
        group = _row_group(row, nict_raw)
        if _held_out(group):
            hold_rows.append(row)
        else:
            ex = _as_example(row)
            if ex is not None:
                train_part.append(ex)

    hold_ex = [(_as_example(r), r) for r in hold_rows]
    hold_ex = [(e, r) for e, r in hold_ex if e is not None]
    print(f"train part: {len(train_part)}   held-out part: {len(hold_ex)}")
    print(f"held-out by source: {dict(Counter(r['source'] for _, r in hold_ex))}\n")

    model = TfidfKnnAxisRegressor(word_ngram_max=2).fit(train_part, require_full_axes=True)

    def run_slice(label: str, pairs: list[tuple[AxisTrainingExample, dict[str, Any]]]) -> None:
        if len(pairs) < 10:
            print(f"[{label:26}] n={len(pairs):4}  (too few, skipped)")
            return
        stored = [{a: int(e.label[a]) for a in AXIS_KEYS} for e, _ in pairs]
        student = [model.predict(e.utterance) for e, _ in pairs]
        teacher = []
        for _, row in pairs:
            payload = {"utterance": row["utterance"]}
            if row.get("sample_bucket"):
                payload["sample_bucket"] = row["sample_bucket"]
            teacher.append(draft_axes(payload))
        s_vs_stored = _agreement(stored, student)
        t_vs_stored = _agreement(stored, teacher)
        s_vs_teacher = _agreement(teacher, student)
        print(f"[{label:26}] n={len(pairs):4}")
        print(f"    student vs stored weak labels : {_fmt(s_vs_stored)}")
        print(f"    draft_axes vs stored labels   : {_fmt(t_vs_stored)}")
        print(f"    student vs draft_axes         : {_fmt(s_vs_teacher)}")

    run_slice("held-out ALL", hold_ex)
    by_source: dict[str, list[tuple[AxisTrainingExample, dict[str, Any]]]] = defaultdict(list)
    for e, r in hold_ex:
        by_source[str(r["source"])].append((e, r))
    for src, pairs in sorted(by_source.items()):
        run_slice(f"held-out {src}", pairs)

    print()
    print("Interpretation:")
    print("  student~stored high + (from Day 1) student~human low  -> supervision ceiling")
    print("  student~stored low  vs draft_axes~stored high         -> representation limit")
    print("  NICT stored labels are codex_accept_draft, so student~stored there is")
    print("  partly circular; weight the AMI / Taskmaster / CHiME rows more.")


if __name__ == "__main__":
    main()
