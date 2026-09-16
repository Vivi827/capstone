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
import logging
import os
import re
from typing import Dict, List, Tuple

import httpx

_FEEDBACK_SYSTEM_PROMPT = '''\
You are Pally, a friendly English conversation tutor.
Extract only corrections already expressed in Pally's reply to the user.
You are recording the conversation's feedback, not performing a new review.

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
- Include a correction only when Pally's reply actually recasts the user's
  mistaken expression in its corrected form. An uncorrected error must NOT
  appear in the output, even if you know how to fix it.
- Copy original verbatim from the user utterance and corrected verbatim from
  Pally's reply. Use short matching spans, not newly reconstructed sentences.
- A reaction, summary, synonym substitution, or change of perspective alone
  is NOT a correction. Return [] if Pally did not correct anything.
- Explain only the recorded correction in Korean; do not add further advice
  or introduce any correction absent from Pally's reply.
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

Examples:
User: "she want cookies"
Pally: "Oh, she wants cookies? What kind does she like?"
Output: [{"original":"she want","corrected":"she wants","explanation_ko":"3인칭 단수 현재형에는 동사에 -s를 붙여요."}]

User: "she want cookies"
Pally: "What kind of cookies?"
Output: []
Reason: Pally did not say "she wants". Do not infer a correction from a question.

User: "I am happy"
Pally: "That is wonderful! What happened?"
Output: []
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


def _feedback_tokens(text: str) -> list[str]:
    # STT punctuation and casing are not corrections. Preserve word boundaries
    # so e.g. "he" cannot match inside "she".
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text.replace("\u2019", "'").casefold())


def _contains_span(source: list[str], span: list[str]) -> bool:
    return bool(span) and any(
        source[i:i + len(span)] == span for i in range(len(source) - len(span) + 1)
    )


def _ground_feedback(items: List[Dict], utterance: str, reply: str) -> List[Dict]:
    user_tokens = _feedback_tokens(utterance)
    reply_tokens = _feedback_tokens(reply)
    grounded = []
    for item in items:
        if not all(isinstance(item.get(key), str) and item[key].strip()
                   for key in ("original", "corrected", "explanation_ko")):
            raise ValueError("Feedback contains invalid fields")
        original = _feedback_tokens(item["original"])
        corrected = _feedback_tokens(item["corrected"])
        if not _contains_span(user_tokens, original) or not _contains_span(reply_tokens, corrected):
            raise ValueError("Feedback correction is not grounded in the conversation")
        if original != corrected:
            grounded.append(item)
    return grounded


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
        items = _call_gemini_feedback(utterance, pally_reply)
        return _ground_feedback(items, utterance, pally_reply), False
    except Exception as exc:
        # Log only the error type: HTTP errors may include credential-bearing URLs.
        logging.warning("Feedback extraction failed: %s", type(exc).__name__)

    # Degraded: rule-based fallback. Still marked failed=True — it's a
    # conservative safety net, not a substitute for real grammar checking.
    try:
        return _ground_feedback(_fallback_rule_based(utterance), utterance, pally_reply), True
    except Exception:
        return [], True


__all__ = ["generate_feedback"]
