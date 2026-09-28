# -*- coding: utf-8 -*-
"""Statistical analysis for the A/B blind-evaluation results (PM final design Sec. 15).

Unit of analysis is the held-out item (20 final-test items), not the 4 raters'
individual judgments (Sec. 15 intro: "통계 단위는 평가자 표가 아니라 최종 실험
20개의 입력 항목이다").

- H1: conditional B win-rate among A-or-B-decided items -> exact sign/binomial
  test + 95% Wilson score CI.
- H2: paired binary outcomes (critical_error, good_response) -> McNemar's exact
  test, implemented as a binomial test on the discordant pairs (mathematically
  equivalent, avoids adding a statsmodels dependency for one test).
- H3 / other 1-5 sub-scores: item-level B-A paired difference -> mean, median,
  bootstrap 95% CI.

These functions are pure statistics -- test them with synthetic data freely.
A dummy run here proves the math, not any real finding (CLAUDE.md Sec.6 #2).

Usage:
  python scripts/analyze_purpose_aware_results.py --verdicts path/to/verdicts.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    from scipy.stats import norm

    z = norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half_width = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / denom
    return (max(0.0, center - half_width), min(1.0, center + half_width))


def h1_conditional_win_rate(verdicts: list[str]) -> dict:
    """verdicts: one of 'A', 'B', 'tie', 'both_bad', 'no_consensus' per item."""
    decided = [v for v in verdicts if v in ("A", "B")]
    b_wins = sum(1 for v in decided if v == "B")
    n = len(decided)
    if n == 0:
        return {"n_decided": 0, "b_win_rate": None, "wilson_ci": None, "binomial_p": None}
    result = binomtest(b_wins, n, p=0.5, alternative="two-sided")
    return {
        "n_decided": n,
        "n_excluded_tie_or_bad": len(verdicts) - n,
        "b_wins": b_wins,
        "b_win_rate": b_wins / n,
        "wilson_ci_95": wilson_ci(b_wins, n),
        "binomial_p_two_sided": result.pvalue,
    }


def h2_mcnemar(a_outcomes: list[bool], b_outcomes: list[bool]) -> dict:
    """McNemar's exact test via binomial test on discordant pairs.
    a_outcomes/b_outcomes: parallel lists of booleans (e.g. critical_error per item)."""
    if len(a_outcomes) != len(b_outcomes):
        raise ValueError("a_outcomes and b_outcomes must be the same length (paired items)")
    a_only = sum(1 for a, b in zip(a_outcomes, b_outcomes) if a and not b)
    b_only = sum(1 for a, b in zip(a_outcomes, b_outcomes) if b and not a)
    discordant = a_only + b_only
    if discordant == 0:
        return {"discordant_pairs": 0, "a_only": 0, "b_only": 0, "exact_p": None}
    result = binomtest(min(a_only, b_only), discordant, p=0.5, alternative="two-sided")
    return {"discordant_pairs": discordant, "a_only": a_only, "b_only": b_only, "exact_p": result.pvalue}


def paired_bootstrap_ci(b_minus_a: list[float], n_boot: int = 10000, seed: int = 0) -> dict:
    arr = np.array(b_minus_a, dtype=float)
    rng = np.random.default_rng(seed)
    boot_means = [rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    return {
        "n_items": len(arr),
        "mean_diff": float(arr.mean()),
        "median_diff": float(np.median(arr)),
        "bootstrap_ci_95": (float(lo), float(hi)),
    }


def analyze(verdicts_path: Path) -> dict:
    rows = [json.loads(l) for l in verdicts_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    report = {
        "h1_conditional_b_win_rate": h1_conditional_win_rate([r["winner"] for r in rows]),
        "full_distribution": {
            k: sum(1 for r in rows if r["winner"] == k) for k in ("A", "B", "tie", "both_bad", "no_consensus")
        },
    }
    if all("critical_error_a" in r and "critical_error_b" in r for r in rows):
        report["h2_critical_error_mcnemar"] = h2_mcnemar(
            [r["critical_error_a"] for r in rows], [r["critical_error_b"] for r in rows]
        )
    if all("good_response_a" in r and "good_response_b" in r for r in rows):
        report["h2_good_response_mcnemar"] = h2_mcnemar(
            [r["good_response_a"] for r in rows], [r["good_response_b"] for r in rows]
        )
    if all("continuity_a" in r and "continuity_b" in r for r in rows):
        diffs = [r["continuity_b"] - r["continuity_a"] for r in rows]
        report["h3_continuity_bootstrap"] = paired_bootstrap_ci(diffs)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdicts", type=Path, required=True,
                         help="jsonl with one row per final-test item: winner, and optionally "
                              "critical_error_a/b, good_response_a/b, continuity_a/b")
    args = parser.parse_args()
    report = analyze(args.verdicts)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
