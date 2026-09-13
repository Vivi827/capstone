# -*- coding: utf-8 -*-
"""Reserve the ML-transition final acceptance-test pool.

Read-only. Recovers NICT provenance via the 1-based ``source_line`` that
``sample_nict_jle_label_candidates.py`` stored on every training row, then
partitions the gold candidate reservoir (minus the already-analysed
dev-200) into:

* ``ml_transition_reserved_final_test_pool.jsonl`` -- rows whose provenance
  group does not overlap the experimental training set *or* the repeatedly
  analysed dev-200, split into ``final_gate`` / ``gate4_reproduction``.
* ``ml_transition_reservation_audit.jsonl`` -- every candidate row with the
  tags used to include or exclude it, so the exclusions stay auditable.

No model scores, draft labels, or human labels are read. This only fixes
the leakage boundary before any further labelling or experiments touch
these groups.

Run from the repository root:
  python scripts/reserve_ml_transition_final_pool.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DEFAULT_TRAINING = Path("data/fixtures/axis_dataset_combined_real_speech_experimental.jsonl")
DEFAULT_NICT_RAW = Path("data/fixtures/nict_jle_learner_utterances.jsonl")
DEFAULT_GOLD_RESERVOIR = Path("data/fixtures/ml_transition_gold_candidates_600.jsonl")
DEFAULT_DEV_200 = Path("data/fixtures/ml_transition_gold_stratified_candidates_200.jsonl")
DEFAULT_POOL_OUTPUT = Path("data/fixtures/ml_transition_reserved_final_test_pool.jsonl")
DEFAULT_AUDIT_OUTPUT = Path("data/fixtures/ml_transition_reservation_audit.jsonl")
DEFAULT_SEED = 20260910
# fraction of clean groups (per source) reserved for the final gate; the
# rest is held for the gate #4 reproduction check.
FINAL_GATE_FRACTION = 0.6
# AMI is a single strict group in the current pool: kept as a reference row,
# never counted toward AMI generalisation (user decision 2026-09-10).
REFERENCE_ONLY_SOURCES = {"ami_real"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_group(row: dict[str, Any]) -> str:
    """Same key on both sides of the leakage comparison. Falls back to the
    utterance only when no real provenance exists -- callers must treat a
    fallback key as 'provenance not verified', never as clean evidence."""
    source = str(row.get("source", "unknown"))
    group = row.get("source_group") or row.get("source_record_id") or row.get("source_file")
    if not group:
        return f"{source}:utt:{str(row['utterance']).strip().casefold()}"
    return f"{source}:{group}"


def recover_nict_training_groups(
    training_rows: list[dict[str, Any]], nict_raw: list[dict[str, Any]]
) -> tuple[set[str], dict[str, int]]:
    """Map every NICT training row to its raw source row by 1-based
    source_line, verifying the utterance matches, and collect the recovered
    provenance groups."""
    groups: set[str] = set()
    stats = Counter()
    for row in training_rows:
        if not str(row.get("source", "")).startswith("nict"):
            continue
        stats["nict_training_rows"] += 1
        source_line = row.get("source_line")
        if source_line is None:
            stats["no_source_line"] += 1
            continue
        index = int(source_line) - 1
        if not (0 <= index < len(nict_raw)):
            stats["source_line_out_of_range"] += 1
            continue
        raw = nict_raw[index]
        if str(raw["utterance"]).strip() != str(row["utterance"]).strip():
            stats["utterance_mismatch"] += 1
            continue
        stats["verified"] += 1
        groups.add(canonical_group(raw))
    return groups, dict(stats)


def training_group_set(training_rows: list[dict[str, Any]], nict_groups: set[str]) -> set[str]:
    groups: set[str] = set(nict_groups)
    for row in training_rows:
        if str(row.get("source", "")).startswith("nict"):
            continue
        if row.get("source_group"):
            groups.add(f"{row.get('source', 'unknown')}:{row['source_group']}")
    return groups


def split_clean_groups(clean_groups_by_source: dict[str, list[str]], seed: int) -> dict[str, str]:
    """Assign each clean group to 'final_gate' or 'gate4_reproduction',
    stratified by source, deterministic under ``seed``."""
    assignment: dict[str, str] = {}
    for source, group_list in clean_groups_by_source.items():
        ordered = sorted(group_list, key=lambda g: hashlib.sha256(f"{seed}|{g}".encode()).hexdigest())
        cut = round(len(ordered) * FINAL_GATE_FRACTION)
        for position, group in enumerate(ordered):
            assignment[group] = "final_gate" if position < cut else "gate4_reproduction"
    return assignment


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--nict-raw", type=Path, default=DEFAULT_NICT_RAW)
    parser.add_argument("--gold-reservoir", type=Path, default=DEFAULT_GOLD_RESERVOIR)
    parser.add_argument("--dev-200", type=Path, default=DEFAULT_DEV_200)
    parser.add_argument("--pool-output", type=Path, default=DEFAULT_POOL_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--expect-nict-raw-sha256",
        default=None,
        help="if set, abort before writing when the NICT raw file hash differs from this baseline",
    )
    parser.add_argument(
        "--expect-training-sha256",
        default=None,
        help="if set, abort before writing when the training file hash differs from this baseline",
    )
    parser.add_argument(
        "--allow-unverified-provenance",
        action="store_true",
        help=(
            "override the fail-safe: proceed even when NICT source_line recovery is "
            "not 100%%. Off by default so a failed recovery can never silently mark a "
            "contaminated row as reserved_clean."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    training_rows = load_jsonl(args.training)
    nict_raw = load_jsonl(args.nict_raw)
    gold_reservoir = load_jsonl(args.gold_reservoir)
    dev_200 = load_jsonl(args.dev_200)

    nict_raw_hash = file_sha256(args.nict_raw)
    training_hash = file_sha256(args.training)

    nict_groups, nict_stats = recover_nict_training_groups(training_rows, nict_raw)
    provenance_verified = (
        nict_stats.get("verified", 0) == nict_stats.get("nict_training_rows", -1)
        and nict_stats.get("nict_training_rows", 0) > 0
    )

    # Fail-safe: the reserved pool is only trustworthy when every NICT training
    # row's provenance group was recovered. A partial recovery means some
    # contaminated groups are invisible to the leakage check, so a train row
    # could be mislabelled reserved_clean. Abort before touching the existing
    # pool file rather than overwrite it with a weaker split.
    hash_errors: list[str] = []
    if args.expect_nict_raw_sha256 and nict_raw_hash != args.expect_nict_raw_sha256:
        hash_errors.append(
            f"NICT raw hash {nict_raw_hash} != expected {args.expect_nict_raw_sha256}"
        )
    if args.expect_training_sha256 and training_hash != args.expect_training_sha256:
        hash_errors.append(
            f"training hash {training_hash} != expected {args.expect_training_sha256}"
        )
    if hash_errors:
        raise SystemExit(
            "ABORT (baseline hash mismatch, existing pool left untouched):\n  "
            + "\n  ".join(hash_errors)
        )
    if not provenance_verified and not args.allow_unverified_provenance:
        raise SystemExit(
            "ABORT: NICT provenance recovery incomplete "
            f"({nict_stats.get('verified', 0)}/{nict_stats.get('nict_training_rows', 0)} rows verified; "
            f"stats={nict_stats}).\n"
            "The reserved pool would be built on an incomplete leakage boundary and could\n"
            "mark a training-contaminated row as reserved_clean. Existing pool file left\n"
            "untouched. Re-run with --allow-unverified-provenance only if you have\n"
            "independently confirmed the NICT rows are safe."
        )

    train_groups = training_group_set(training_rows, nict_groups)
    dev_utterances = {str(row["utterance"]).strip() for row in dev_200}
    dev_groups = {canonical_group(row) for row in dev_200}

    remaining = [row for row in gold_reservoir if str(row["utterance"]).strip() not in dev_utterances]

    audit_rows: list[dict[str, Any]] = []
    clean_rows: list[dict[str, Any]] = []
    clean_groups_by_source: dict[str, list[str]] = {}
    for row in remaining:
        group = canonical_group(row)
        train_overlap = group in train_groups
        dev_overlap = group in dev_groups
        has_real_group = bool(row.get("source_group") or row.get("source_record_id") or row.get("source_file"))
        if train_overlap and dev_overlap:
            exposure = "train_and_dev"
        elif train_overlap:
            exposure = "train_contaminated"
        elif dev_overlap:
            exposure = "dev_analyzed"
        else:
            exposure = "reserved_clean"

        tagged = dict(row)
        tagged["canonical_group"] = group
        tagged["train_overlap"] = train_overlap
        tagged["dev_overlap"] = dev_overlap
        tagged["provenance_verified"] = bool(has_real_group and provenance_verified)
        tagged["exposure_status"] = exposure
        audit_rows.append(tagged)

        if exposure == "reserved_clean":
            clean_groups_by_source.setdefault(str(row.get("source", "unknown")), [])
            if group not in clean_groups_by_source[str(row.get("source", "unknown"))]:
                clean_groups_by_source[str(row.get("source", "unknown"))].append(group)
            clean_rows.append(tagged)

    group_role = split_clean_groups(clean_groups_by_source, args.seed)
    pool_rows: list[dict[str, Any]] = []
    for row in clean_rows:
        enriched = dict(row)
        enriched["reservation_role"] = group_role[row["canonical_group"]]
        enriched["reference_only"] = str(row.get("source", "")) in REFERENCE_ONLY_SOURCES
        enriched["reservation_seed"] = args.seed
        enriched["nict_raw_sha256"] = nict_raw_hash
        enriched["training_sha256"] = training_hash
        pool_rows.append(enriched)

    write_jsonl(pool_rows, args.pool_output)
    write_jsonl(audit_rows, args.audit_output)

    print(f"nict_source_line_recovery: {nict_stats}")
    print(f"provenance_verified (all NICT rows matched): {provenance_verified}")
    print(f"recovered_nict_training_groups: {len(nict_groups)}")
    print(f"total_training_groups: {len(train_groups)}")
    print(f"remaining (gold reservoir minus dev-200): {len(remaining)}")
    print()
    exposure_counts = Counter(row["exposure_status"] for row in audit_rows)
    for status in ("reserved_clean", "train_contaminated", "dev_analyzed", "train_and_dev"):
        by_source = Counter(str(r["source"]) for r in audit_rows if r["exposure_status"] == status)
        print(f"  {status}: {exposure_counts[status]}  {dict(by_source)}")
    print()
    reserved_by_source = Counter(str(r["source"]) for r in pool_rows)
    role_counts = Counter(r["reservation_role"] for r in pool_rows)
    print(f"reserved pool rows: {len(pool_rows)}  by source: {dict(reserved_by_source)}")
    print(f"reserved groups: {len(group_role)}  roles: {dict(role_counts)}")
    for role in ("final_gate", "gate4_reproduction"):
        by_source = Counter(str(r["source"]) for r in pool_rows if r["reservation_role"] == role)
        print(f"  {role}: {dict(by_source)}")
    ref_only = sum(1 for r in pool_rows if r["reference_only"])
    print(f"reference_only rows (AMI, not counted toward generalisation): {ref_only}")
    print()
    print(f"pool_output: {args.pool_output}")
    print(f"audit_output: {args.audit_output}")


if __name__ == "__main__":
    main()
