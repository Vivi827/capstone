# -*- coding: utf-8 -*-
"""
generate_feedback
-----------------
Provide a synchronous function to generate FeedbackItem list for a given
utterance + pally reply. Attempts to call Gemini (if `GOOGLE_AI_API_KEY` is
configured).

Public API:
  generate_feedback(utterance: str, pally_reply: str, level: str) -> tuple[list[dict], bool]

Returns `(items, failed)`:
  - `failed=False`: Gemini ran successfully. `items` may be `[]` — that is a
    normal result meaning no correction was needed, not an error.
  - `failed=True`: Gemini was unreachable/unconfigured/unparseable. `items`
    is a best-effort rule-based fallback (possibly `[]`). Callers should
    surface this as a `feedback_failed` warning and keep the turn `partial`
    rather than treating an empty `items` as "nothing to correct".

Returned FeedbackItem dict shape:
  { "original": str, "corrected": str, "explanation_ko": str }
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import httpx

_FEEDBACK_SYSTEM_PROMPT = '''\
You are Pally, a friendly English conversation tutor.
Analyze the user's utterance and provide structured feedback.

Return ONLY valid JSON with exactly these three fields or an array of items:
[
  {
    "original": "<original substring>",
    "corrected": "<corrected expression>",
    "explanation_ko": "<short Korean explanation>"
  }
]

Context:
- The utterance is a speech-to-text (STT) transcript of spoken conversation
  practice, not written text the user typed.
- STT transcripts naturally have no sentence-initial capitalization and no
  end punctuation (periods, question marks, commas). That is a transcription
  artifact, not something the user got wrong.
- Judge the utterance against spoken conversational English norms (구어체),
  not formal written English norms (문어체).
- "Pally" (or whatever name the user calls their conversation partner) is
  the tutor's own name — a proper noun, never a misspelled word.

Rules:
- NEVER flag capitalization or punctuation (periods, commas, question marks)
  as something to correct. Ignore these entirely, even when other real
  issues are present in the same sentence.
- NEVER flag proper nouns, names, or the tutor's own name as a spelling or
  word-choice error.
- Only return items for genuine grammar mistakes, verb tense/agreement
  errors, or unnatural word choice — things that would still sound wrong in
  casual spoken English.
- If the user's utterance does not need correction (once capitalization and
  punctuation are ignored), return an empty array []
- Keep each explanation_ko brief (1-2 sentences)
'''


def _parse_json_from_candidate(candidate_text: str):
    text = candidate_text.strip()
    # remove Markdown code fence if present
    if text.startswith('```'):
        parts = text.split('\n', 1)
        if len(parts) > 1:
            text = parts[1].rsplit('```', 1)[0].strip()
    # Try to load JSON; it may be an object or an array
    return json.loads(text)


def _call_gemini_feedback(utterance: str, pally_reply: str) -> List[Dict]:
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key:
        raise RuntimeError('GOOGLE_AI_API_KEY not configured')

    user_prompt = (
        f'User utterance: "{utterance}"\n'
        f'Pally replied: "{pally_reply}"\n\n'
        'Provide JSON array of feedback items as described.'
    )

    payload = {
        "system_instruction": {"parts": [{"text": _FEEDBACK_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
            "maxOutputTokens": 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash-lite:generateContent?key=" + api_key
    )

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f'Gemini error {resp.status_code}: {resp.text}')

    resp_json = resp.json()
    candidates = resp_json.get('candidates', [])
    if not candidates:
        return []
    parts = candidates[0].get('content', {}).get('parts', [])
    raw = ' '.join(p.get('text', '') for p in parts if not p.get('thought', False)).strip()
    if not raw:
        return []

    parsed = _parse_json_from_candidate(raw)
    # normalize to list of dicts
    if isinstance(parsed, dict):
        # if returned single feedback object with keys like correction/tone_feedback
        # map to expected shape if possible
        if set(parsed.keys()) >= {"correction"}:
            return [
                {
                    "original": utterance,
                    "corrected": parsed.get("correction", ""),
                    "explanation_ko": parsed.get("tone_feedback", ""),
                }
            ]
        # otherwise try to interpret dict as a single FeedbackItem
        if set(parsed.keys()) >= {"original", "corrected", "explanation_ko"}:
            return [parsed]
        return []
    if isinstance(parsed, list):
        # validate items
        out: List[Dict] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if all(k in item for k in ("original", "corrected", "explanation_ko")):
                out.append({
                    "original": item["original"],
                    "corrected": item["corrected"],
                    "explanation_ko": item["explanation_ko"],
                })
        return out
    return []


def _fallback_rule_based(utterance: str) -> List[Dict]:
    """Very small rule-based fallback corrections for common patterns.

    This is intentionally conservative: prefer returning [] if unsure.
    """
    text = utterance.strip()
    # simple pattern: "i had no X" -> "i didn't have X" and/or "i skipped X"
    import re

    # Case-insensitive match against the original text (not a lowercased
    # copy) so casing is preserved, and stop at the first sentence boundary
    # so a trailing second sentence isn't swallowed into the correction.
    m = re.search(r"i had no ([^.!?]+)", text, flags=re.IGNORECASE)
    if m:
        obj = m.group(1).strip()
        corrected = f"I didn't have {obj}."
        explanation = f"'{text}'보다 '{corrected}'가 더 자연스럽습니다."
        return [{"original": text, "corrected": corrected, "explanation_ko": explanation}]

    # contraction suggestion: "i'm" -> "i am" is not necessarily correction; skip

    return []


def generate_feedback(utterance: str, pally_reply: str, level: str) -> Tuple[List[Dict], bool]:
    """Generate structured feedback items for a single user turn.

    Returns `(items, failed)` — see module docstring for the failed-flag
    contract. `failed=True` means the primary (Gemini) path did not
    complete; callers should not read an empty `items` as "no correction
    needed" in that case.
    """
    # Basic validation — not a generation failure, just nothing to do.
    if not utterance or not isinstance(utterance, str):
        return [], False

    # Primary: model-based generation. Any failure (missing key, network,
    # bad response) means we could not reliably determine feedback.
    try:
        api_key = os.getenv('GOOGLE_AI_API_KEY')
        if not api_key:
            raise RuntimeError('GOOGLE_AI_API_KEY not configured')
        return _call_gemini_feedback(utterance, pally_reply), False
    except Exception:
        pass

    # Degraded: rule-based fallback. Still marked failed=True — it's a
    # conservative safety net, not a substitute for real grammar checking.
    try:
        return _fallback_rule_based(utterance), True
    except Exception:
        return [], True


__all__ = ["generate_feedback"]
