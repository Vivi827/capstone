# -*- coding: utf-8 -*-
"""Aggregate the 4 completed labeling workbooks into consensus labels (PM design Sec. 9.2)
and compute inter-rater reliability (Sec. 9.3), then merge into the items jsonl so
scripts/train_purpose_axis_models.py can run directly.

Purpose: majority vote (>=3 of the raters who scored that item). Ties/no-majority
are left as label_source="no_consensus" for manual review, never auto-decided.
Axes: median of the raters who scored that item, rounded to nearest 5.

Column layout is read dynamically per file (header row located by searching for
'item_id', not assumed at a fixed row/position) because the 4 real files came
back with different header rows/column orders after round-tripping through
different spreadsheet apps (Numbers export reshuffled slot A; slot B has one
header cell overwritten by a stray data value) -- confirmed by hand inspection
before writing this script, not assumed.

Usage:
  python scripts/aggregate_pally_purpose_v1_labels.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
import openpyxl
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "data/fixtures/pally_purpose_v1_items_100.jsonl"
SLOT_REVIEWERS = {"A": "윤서", "B": "minju", "C": "eunheay", "D": "chanhee"}
AXES = ["Formality", "Humor", "Curiosity"]
ANSWER_KEY_FIELDS = ["required_properties", "forbidden_errors", "continuation_anchors", "continuation_probe"]
FINAL_TEST_IDS = {f"pally100_{i:03d}" for i in (34, *range(81, 88), *range(89, 101))}
PURPOSE_CODES = {
    "answer_inform", "explain_explore", "act_request",
    "confirm_repair", "acknowledge_empathize", "social_reciprocate",
}


def load_slot(slot: str) -> dict:
    path = ROOT / f"data/fixtures/pally_purpose_v1_scoring_slot{slot}.xlsx"
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["채점 시트"]

    header_row = None
    headers = None
    for r in range(1, 10):
        vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if "item_id" in vals:
            header_row, headers = r, vals
            break
    if header_row is None:
        raise ValueError(f"slot {slot}: no header row found")

    col_of = {}
    for i, h in enumerate(headers):
        if h and h not in col_of:
            col_of[h] = i + 1

    rows = {}
    for r in range(header_row + 1, ws.max_row + 1):
        item_id = ws.cell(row=r, column=col_of.get("item_id", 1)).value
        if not item_id:
            continue
        row = {name: ws.cell(row=r, column=c).value for name, c in col_of.items()}
        rows[item_id] = row
    return rows


def fleiss_kappa(votes_per_item: list[dict[str, int]], categories: list[str]) -> float:
    """votes_per_item: one dict per item mapping category -> count of raters choosing it."""
    n_items = len(votes_per_item)
    n_raters = sum(votes_per_item[0].values())
    p_j = {c: sum(v.get(c, 0) for v in votes_per_item) / (n_items * n_raters) for c in categories}
    P_i = []
    for v in votes_per_item:
        n_i = sum(v.values())
        P_i.append((sum(v.get(c, 0) ** 2 for c in categories) - n_i) / (n_i * (n_i - 1)))
    P_bar = sum(P_i) / n_items
    P_e = sum(p ** 2 for p in p_j.values())
    if P_e == 1:
        return float("nan")
    return (P_bar - P_e) / (1 - P_e)


def icc_1k(scores: np.ndarray) -> float:
    """scores: (n_items, n_raters), fully balanced (no missing). One-way random-effects ICC(1,k)."""
    n, k = scores.shape
    grand_mean = scores.mean()
    row_means = scores.mean(axis=1)
    ss_between = k * np.sum((row_means - grand_mean) ** 2)
    ms_between = ss_between / (n - 1)
    ss_within = np.sum((scores - row_means[:, None]) ** 2)
    ms_within = ss_within / (n * (k - 1))
    if ms_between == 0:
        return float("nan")
    return (ms_between - ms_within) / ms_between


def main() -> None:
    slots = {s: load_slot(s) for s in "ABCD"}
    items = [json.loads(l) for l in ITEMS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    report = []
    no_consensus_purpose = []
    answer_key_source = {}

    for item in items:
        iid = item["item_id"]
        purpose_votes = []
        axis_votes = {a: [] for a in AXES}
        for slot, rows in slots.items():
            row = rows.get(iid)
            if not row:
                continue
            p = row.get("purpose_primary")
            if p:
                purpose_votes.append(p)
            for a in AXES:
                v = row.get(a)
                if v is not None and v != "":
                    axis_votes[a].append(float(v))

        # purpose: majority of >=3 among however many actually voted
        counts = {p: purpose_votes.count(p) for p in set(purpose_votes)}
        top = max(counts.items(), key=lambda kv: kv[1]) if counts else (None, 0)
        if top[1] >= 3:
            item["purpose_primary"] = top[0]
            item["label_source"] = "human_consensus"
        else:
            item["purpose_primary"] = None
            item["label_source"] = "no_consensus"
            no_consensus_purpose.append((iid, counts))

        for a in AXES:
            vals = axis_votes[a]
            key = a.lower()
            if vals:
                med = statistics.median(vals)
                item[key] = round(med / 5) * 5
            else:
                item[key] = None
        item["_raw_purpose_votes"] = counts
        item["_raw_axis_votes"] = {a: axis_votes[a] for a in AXES}

        if iid in FINAL_TEST_IDS:
            for f in ANSWER_KEY_FIELDS:
                for slot, rows in slots.items():
                    row = rows.get(iid)
                    if row and row.get(f):
                        item[f] = row[f]
                        answer_key_source.setdefault(iid, {})[f] = slot
                        break

    ITEMS_PATH.write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n", encoding="utf-8"
    )

    # --- reliability stats ---
    report.append("=== 목적(purpose) 신뢰도 ===")
    full4_items = []
    for item in items:
        iid = item["item_id"]
        votes = {slot: slots[slot].get(iid, {}).get("purpose_primary") for slot in "ABCD"}
        if all(votes.values()):
            full4_items.append(votes)
    if full4_items:
        vote_dicts = []
        for votes in full4_items:
            d = {}
            for p in votes.values():
                d[p] = d.get(p, 0) + 1
            vote_dicts.append(d)
        kappa = fleiss_kappa(vote_dicts, sorted(PURPOSE_CODES))
        # simple pairwise agreement rate
        pairs = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]
        agree_rates = []
        for x, y in pairs:
            same = sum(1 for votes in full4_items if votes[x] == votes[y])
            agree_rates.append(same / len(full4_items))
        report.append(f"4인 전부 응답한 항목 수: {len(full4_items)}")
        report.append(f"Fleiss' kappa: {kappa:.3f}")
        report.append(f"평균 쌍별 일치율: {sum(agree_rates)/len(agree_rates):.1%}")
        report.append(f"3인 이상 다수결로 합의된 항목: {sum(1 for it in items if it['label_source']=='human_consensus')}/100")
        report.append(f"합의 실패(no_consensus) 항목: {len(no_consensus_purpose)} -> {no_consensus_purpose}")

    report.append("\n=== 3축 신뢰도 ===")
    for a in AXES:
        full4 = []
        for item in items:
            iid = item["item_id"]
            vals = [slots[s].get(iid, {}).get(a) for s in "ABCD"]
            if all(v is not None and v != "" for v in vals):
                full4.append([float(v) for v in vals])
        arr = np.array(full4)
        icc = icc_1k(arr)
        pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        maes = [np.mean(np.abs(arr[:, i] - arr[:, j])) for i, j in pairs]
        spearmans = [spearmanr(arr[:, i], arr[:, j]).correlation for i, j in pairs]
        report.append(
            f"{a}: n={len(arr)}, ICC(1,k)={icc:.3f}, 평균 MAE={np.mean(maes):.1f}점, "
            f"평균 Spearman={np.mean(spearmans):.3f}"
        )

    report.append("\n=== 최종실험 20개 응답 채점 기준 출처 ===")
    for iid, sources in sorted(answer_key_source.items()):
        report.append(f"{iid}: {sources}")

    out_path = ROOT / "docs/plan/2026-09-29-pally-purpose-v1-label-reliability-report.md"
    out_path.write_text("# Pally Purpose-Aware v1 라벨 신뢰도 리포트 (2026-09-29)\n\n```\n" + "\n".join(report) + "\n```\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\n merged consensus labels into {ITEMS_PATH}")
    print(f" wrote reliability report to {out_path}")


if __name__ == "__main__":
    main()
