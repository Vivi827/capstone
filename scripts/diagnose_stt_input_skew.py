# -*- coding: utf-8 -*-
"""Days 2-3 diagnosis E3-ablation: train/serve input skew from Google STT.

Verified in `backend/main.py`: the STT request sets
`"enableAutomaticPunctuation": False`, and the transcript goes straight to
`_analyze_axes(transcript)` with no normalization. So in production the axis
analyzers receive text with **no punctuation** (and possibly lowercased,
depending on the `latest_long` / `latest_short` model -- confirm with a real
call).

The dev-200 and training corpora all have proper punctuation and case. The
rule analyzer and `draft_axes` key on `?` (Curiosity), `!` (Energy), and
capital-letter emphasis. Those signals are dead at serve time.

This script re-runs rule / ML / hybrid on dev-200 under three input
conditions to size the skew:
  * as-is                (matches current eval, NOT production)
  * punctuation stripped (matches STT with automatic punctuation off)
  * punct stripped + lowercased (matches STT if latest_long also lowercases)

Training set is dev-group-purged (cycle 4b). No human labels created.

Run from the repository root:
  python scripts/diagnose_stt_input_skew.py
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.analyzers import RuleBasedAxisAnalyzer
from ai.contracts import AXIS_KEYS
from ai.ml_baseline import AxisTrainingExample, TfidfKnnAxisRegressor, _validate_axes
from scripts.reserve_ml_transition_final_pool import (
    canonical_group,
    recover_nict_training_groups,
    training_group_set,
)

TRAIN_PATH = Path(ROOT) / "data" / "fixtures" / "axis_dataset_combined_real_speech_experimental.jsonl"
NICT_RAW_PATH = Path(ROOT) / "data" / "fixtures" / "nict_jle_learner_utterances.jsonl"
GOLD_PATH = Path(ROOT) / "data" / "fixtures" / "ml_transition_gold_human_200.jsonl"

_PUNCT = re.compile(r"[.,!?;:\"’“”()\-]+")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def strip_punct(text: str) -> str:
    return re.sub(r"\s+", " ", _PUNCT.sub(" ", text)).strip()


def strip_punct_lower(text: str) -> str:
    return strip_punct(text).lower()


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


def _as_examples(rows: list[dict[str, Any]], transform: Callable[[str], str]) -> list[AxisTrainingExample]:
    out = []
    for r in rows:
        try:
            label = _validate_axes(r["axes"])
        except (KeyError, ValueError):
            continue
        out.append(
            AxisTrainingExample(
                utterance=transform(str(r["utterance"])),
                label=label,
                style=str(r.get("style", "conversation")),
                source=str(r.get("source", "")),
                source_group=str(r.get("source_group", "")),
            )
        )
    return out


def _score(gold: list[dict[str, Any]], preds: list[dict[str, int]], idx: list[int] | None = None) -> dict[str, Any]:
    idx = idx if idx is not None else list(range(len(gold)))
    per_mae: dict[str, float] = {}
    per_rho: dict[str, float] = {}
    for axis in AXIS_KEYS:
        e = [float(gold[i]["axes"][axis]) for i in idx]
        p = [float(preds[i][axis]) for i in idx]
        per_mae[axis] = sum(abs(pp - ee) for ee, pp in zip(e, p)) / len(e)
        per_rho[axis] = _spearman(e, p)
    valid = [v for v in per_rho.values() if not math.isnan(v)]
    na = [a for a, v in per_rho.items() if math.isnan(v)]
    return {"mae": sum(per_mae.values()) / len(per_mae),
            "rho": sum(valid) / len(valid) if valid else float("nan"), "na": na}


def _fmt(s: dict[str, Any]) -> str:
    rho = "n/a" if math.isnan(s["rho"]) else f"{s['rho']:.3f}"
    na = f" (na {','.join(s['na'])})" if s["na"] else ""
    return f"MAE {s['mae']:6.3f}  rho {rho:>6}{na}"


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    nict_raw = load_jsonl(NICT_RAW_PATH)
    gold = load_jsonl(GOLD_PATH)

    ng, stats = recover_nict_training_groups(train_rows, nict_raw)
    if stats.get("verified") != stats.get("nict_training_rows"):
        raise SystemExit(f"NICT provenance incomplete: {stats}")
    tgroups = training_group_set(train_rows, ng)
    dev_groups = {canonical_group(r) for r in gold}

    def rg(r: dict[str, Any]) -> str:
        if str(r.get("source", "")).startswith("nict"):
            sl = r.get("source_line")
            if sl is not None and 0 <= int(sl) - 1 < len(nict_raw):
                raw = nict_raw[int(sl) - 1]
                if str(raw["utterance"]).strip() == str(r["utterance"]).strip():
                    return canonical_group(raw)
        return canonical_group(r)

    purged = [r for r in train_rows if rg(r) not in dev_groups]

    # fraction of dev/train text that even has punctuation to lose
    dev_q = sum(1 for r in gold if "?" in r["utterance"])
    dev_bang = sum(1 for r in gold if "!" in r["utterance"])
    print(f"dev-200 rows with '?': {dev_q}/200   with '!': {dev_bang}/200")
    print(f"backend STT: enableAutomaticPunctuation=False (backend/main.py), no normalization before _analyze_axes\n")

    conditions = {
        "as-is (current eval)": lambda s: s,
        "punct stripped (STT)": strip_punct,
        "punct+lowercase": strip_punct_lower,
    }

    by_source: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(gold):
        by_source[r["source"]].append(i)

    for cond_name, tf in conditions.items():
        rule = RuleBasedAxisAnalyzer()
        rule_p = [rule.analyze(tf(r["utterance"])).to_axes_dict() for r in gold]
        train_ex = _as_examples(purged, tf)
        model = TfidfKnnAxisRegressor(word_ngram_max=2).fit(train_ex, require_full_axes=True)
        ml_p = [model.predict(tf(r["utterance"])) for r in gold]
        hy_p = [{a: round((rp[a] + mp[a]) / 2) for a in AXIS_KEYS} for rp, mp in zip(rule_p, ml_p)]

        print(f"--- {cond_name} ---")
        print(f"  rule   {_fmt(_score(gold, rule_p))}")
        print(f"  ML     {_fmt(_score(gold, ml_p))}")
        print(f"  hybrid {_fmt(_score(gold, hy_p))}")
        for src, idx in sorted(by_source.items()):
            print(f"    {src:26} rule {_fmt(_score(gold, rule_p, idx))}   ML {_fmt(_score(gold, ml_p, idx))}   hyb {_fmt(_score(gold, hy_p, idx))}")
        print()

    print("Reading: if rule/hybrid drop sharply from 'as-is' to 'punct stripped' while ML holds,")
    print("the current dev-200 eval over-credits the rule path relative to production, and the")
    print("honest serve-time comparison favours ML/hybrid more than the as-is numbers show.")


if __name__ == "__main__":
    main()
