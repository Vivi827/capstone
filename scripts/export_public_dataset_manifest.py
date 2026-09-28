# -*- coding: utf-8 -*-
"""Produce the GitHub-safe manifest of the 100-item dataset.

PM decision (2026-09-24): the Santa Barbara Corpus is CC BY-ND 3.0 (no
redistribution of derived/trimmed text), so GitHub may only get item ID,
source, label schema, and extraction method for Santa Barbara items -- never
the raw or trimmed sentences. AMI/ICSI are CC BY 4.0 and may keep their text
public. All 40 ambiguous_informal items are Santa Barbara-sourced; the other
60 (clear, surface_shortcut) are AMI/ICSI.

Usage:
  python scripts/export_public_dataset_manifest.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/fixtures/pally_purpose_v1_items_100.jsonl"
OUT = ROOT / "data/fixtures/pally_purpose_v1_items_100_public.jsonl"

# fields that may directly quote or closely paraphrase source text
TEXT_FIELDS = [
    "context_before", "target_turn", "reference_response",
    "intended_slang_sense", "axis_rationale", "purpose_rationale",
    "sense_rationale", "required_properties", "forbidden_errors",
    "continuation_anchors", "continuation_probe",
]

ND_LICENSED_SLICE = "ambiguous_informal"  # Santa Barbara Corpus, CC BY-ND 3.0


def main() -> None:
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    redacted = 0
    for r in rows:
        # internal curation bookkeeping (underscore-prefixed) is never part of
        # the public schema and sometimes quotes source text (e.g. the
        # _replacement_reason notes written during the audit fix pass) -- drop
        # it for every item, not just Santa Barbara ones.
        for key in [k for k in r if k.startswith("_") and k != "_slice_candidate"]:
            del r[key]

        if r.get("_slice_candidate") == ND_LICENSED_SLICE:
            for field in TEXT_FIELDS:
                if r.get(field) is not None:
                    r[field] = None
            r["_text_redacted_reason"] = (
                "Santa Barbara Corpus of Spoken American English is CC BY-ND 3.0; "
                "raw/trimmed text is withheld from the public repo per PM policy "
                "(2026-09-24). Use source_id with corpus access to look up the text."
            )
            redacted += 1

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows ({redacted} text-redacted) -> {OUT}")


if __name__ == "__main__":
    main()
