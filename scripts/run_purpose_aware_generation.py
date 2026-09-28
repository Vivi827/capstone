# -*- coding: utf-8 -*-
"""Generate condition A/B responses for the final-test items (PM final design Sec. 10.4).

Both conditions use the SAME predicted axis scores from the trained common axis
regressor. Condition B additionally receives the predicted communicative purpose.
Neither condition sees `continuation_probe`, and only `context_before` (not full
history) is passed -- per Sec. 10.4 / Sec. 16.1's manipulation checks.

Response generation calls Gemini via the same httpx/API-key pattern as
scripts/flash_lite_axis_teacher.py (key from backend/.env or GOOGLE_AI_API_KEY).
Pass --dry-run to use a stub generator instead of a real call, for testing the
condition-A/B payload-construction logic itself before spending real API calls --
per CLAUDE.md Sec.4, an actual Gemini call must be run and inspected by hand
before this is used for real, --dry-run output is not a substitute for that.

Usage:
  python scripts/run_purpose_aware_generation.py --dry-run   # test plumbing only
  python scripts/run_purpose_aware_generation.py             # real Gemini calls
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

import httpx
import joblib
from scipy.sparse import hstack

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gemini-2.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

SYSTEM_PROMPT_BASE = """You are Pally, replying to one user turn in a casual chat.
Reply in one short natural sentence (about 10-20 words). Do not ask a question unless it is the only natural reaction.
Match the user's Formality/Humor/Curiosity levels given below without imitating any rudeness or unsafe content.
Formality={formality} Humor={humor} Curiosity={curiosity} (0-100 each).
"""
PURPOSE_LINE = "The user's turn most likely intends: {purpose} (respond appropriately for that intent).\n"


def load_key() -> str:
    key = os.getenv("GOOGLE_AI_API_KEY")
    if not key:
        env_path = ROOT / "backend" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GOOGLE_AI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("GOOGLE_AI_API_KEY not found in env or backend/.env")
    return key


def gemini_generate(system_prompt: str, context_before: str | None, target_turn: str, key: str) -> str:
    contents = []
    if context_before:
        contents.append({"role": "user", "parts": [{"text": context_before}]})
    contents.append({"role": "user", "parts": [{"text": target_turn}]})
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0},
    }
    resp = httpx.post(ENDPOINT, params={"key": key}, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def stub_generate(system_prompt: str, context_before: str | None, target_turn: str, key: str) -> str:
    return f"[DRY-RUN STUB] would reply to: {target_turn[:40]!r}"


def build_payload(item: dict, predicted_purpose: str, predicted_axes: dict, condition: str) -> dict:
    """Assemble the generator input for one item/condition. Returns the exact
    payload logged for the manipulation check (Sec. 16.1): A and B must show the
    identical `predicted_axes`, and only B may carry a non-null `predicted_purpose`.
    """
    system_prompt = SYSTEM_PROMPT_BASE.format(**predicted_axes)
    if condition == "purpose_aware":
        system_prompt += PURPOSE_LINE.format(purpose=predicted_purpose)
    return {
        "item_id": item["item_id"],
        "condition": condition,
        "context_before": item.get("context_before"),
        "target_turn": item["target_turn"],
        "predicted_purpose": predicted_purpose if condition == "purpose_aware" else None,
        "predicted_axes": predicted_axes,
        "system_prompt": system_prompt,
    }


def run(items_path: Path, models_path: Path, out_path: Path, generate_fn: Callable) -> list[dict]:
    rows = [json.loads(l) for l in items_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    final_items = [r for r in rows if r.get("split") == "final_test"]
    if not final_items:
        raise ValueError("no split=='final_test' rows found -- is the split assigned?")

    bundle = joblib.load(models_path)
    texts = [r["target_turn"] for r in final_items]
    X = hstack([bundle["word_vec"].transform(texts), bundle["char_vec"].transform(texts)])
    purpose_pred = bundle["purpose_clf"].predict(X)

    key = None if generate_fn is stub_generate else load_key()
    results = []
    for i, item in enumerate(final_items):
        axes = {}
        for axis, model in bundle["axis_models"].items():
            raw = float(model.predict(X[i])[0])
            axes[axis] = round(max(0.0, min(100.0, raw)) / 5) * 5
        purpose = str(purpose_pred[i])

        payload_a = build_payload(item, purpose, axes, "direct")
        payload_b = build_payload(item, purpose, axes, "purpose_aware")
        assert payload_a["predicted_axes"] == payload_b["predicted_axes"], "A/B axis mismatch -- manipulation check failed"
        assert payload_a["predicted_purpose"] is None and payload_b["predicted_purpose"] == purpose

        response_a = generate_fn(payload_a["system_prompt"], item.get("context_before"), item["target_turn"], key)
        response_b = generate_fn(payload_b["system_prompt"], item.get("context_before"), item["target_turn"], key)
        results.append({**payload_a, "response": response_a, "_pair_id": item["item_id"]})
        results.append({**payload_b, "response": response_b, "_pair_id": item["item_id"]})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, default=Path("data/fixtures/pally_purpose_v1_items_100.jsonl"))
    parser.add_argument("--models", type=Path, default=Path("data/models/purpose_axis_models.joblib"))
    parser.add_argument("--out", type=Path, default=Path("data/fixtures/pally_purpose_v1_responses.jsonl"))
    parser.add_argument("--dry-run", action="store_true", help="use a stub generator, no real API calls")
    args = parser.parse_args()

    generate_fn = stub_generate if args.dry_run else gemini_generate
    results = run(args.items, args.models, args.out, generate_fn)
    print(f"generated {len(results)} responses ({len(results)//2} A/B pairs) -> {args.out}")
    if args.dry_run:
        print("NOTE: --dry-run used a stub generator. A real Gemini call must be run and")
        print("      hand-inspected before this is used for the actual experiment (CLAUDE.md Sec.4).")


if __name__ == "__main__":
    main()
