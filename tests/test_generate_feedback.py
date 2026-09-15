# -*- coding: utf-8 -*-
from ai.generate_feedback import generate_feedback
import ai.generate_feedback as feedback_module
import pytest


def _item(original, corrected):
    return {"original": original, "corrected": corrected, "explanation_ko": "주어에 맞춰 동사를 바꿔요."}


def test_review_records_correction_actually_spoken(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    item = _item("she want", "she wants")
    monkeypatch.setattr(feedback_module, "_call_gemini_feedback", lambda *args: [item])
    assert generate_feedback("she want cookies", "Oh, she wants cookies? What kind?", "B1") == ([item], False)


@pytest.mark.parametrize("original, corrected, reply", [
    ("she want", "she wants", "What kind of cookies?"),
    ("he want", "she wants", "Oh, she wants cookies?"),
    ("she want", "he wants", "Oh, she wants cookies?"),
])
def test_ungrounded_correction_is_not_saved(monkeypatch, original, corrected, reply):
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(feedback_module, "_call_gemini_feedback", lambda *args: [_item(original, corrected)])
    items, failed = generate_feedback("she want cookies", reply, "B1")
    assert items == []
    assert failed is True


def test_punctuation_only_change_is_not_a_review_item(monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(feedback_module, "_call_gemini_feedback", lambda *args: [_item("she wants cookies", "She wants cookies!")])
    assert generate_feedback("she wants cookies", "She wants cookies!", "B1") == ([], False)


def test_failed_provider_cannot_introduce_unspoken_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    assert generate_feedback("I had no lunch.", "What would you like to eat?", "B1") == ([], True)


def test_generate_feedback_no_api_key_returns_failed_true(monkeypatch):
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    utterance = "I had no lunch. I'm on a diet."
    pally = "Oh no, you skipped lunch because you're on a diet? What would you like to eat later?"

    items, failed = generate_feedback(utterance, pally, "B1")

    assert failed is True
    assert isinstance(items, list)
    if items:
        item = items[0]
        assert all(k in item for k in ("original", "corrected", "explanation_ko"))


def test_generate_feedback_empty_utterance_is_not_a_failure():
    items, failed = generate_feedback("", "reply", "B1")

    assert items == []
    assert failed is False
