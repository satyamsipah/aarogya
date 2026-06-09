"""Tests for the diagnosis guardrail."""
from app.rag.guardrail import apply_guardrail, has_definitive_diagnosis, DISCLAIMER


# ── apply_guardrail softens definitive language ─────────────────────────────

def test_you_have_softened():
    result = apply_guardrail("You have Type 2 Diabetes.")
    assert "you may have" in result.lower()

def test_diagnosed_with_softened():
    result = apply_guardrail("You are diagnosed with hypertension.")
    assert "you are diagnosed with" not in result.lower()

def test_diagnosis_is_softened():
    result = apply_guardrail("The diagnosis is pneumonia.")
    assert "the diagnosis is" not in result.lower()

def test_safe_sentence_unchanged():
    safe = "These findings may suggest hypertension; discuss with your clinician."
    assert apply_guardrail(safe) == safe


# ── has_definitive_diagnosis detection ─────────────────────────────────────

def test_detects_you_have():
    assert has_definitive_diagnosis("You have diabetes.")

def test_detects_you_are_diagnosed():
    assert has_definitive_diagnosis("You are diagnosed with asthma.")

def test_detects_definitely_have():
    assert has_definitive_diagnosis("You definitely have hypertension.")

def test_no_flag_on_safe_text():
    safe = "This may suggest Type 2 Diabetes — please discuss with your clinician."
    assert not has_definitive_diagnosis(safe)

def test_guardrail_clears_detection():
    """apply_guardrail must produce text that passes has_definitive_diagnosis=False."""
    texts = [
        "You have Type 2 Diabetes.",
        "You are diagnosed with hypertension.",
        "The diagnosis is pneumonia.",
        "You definitely have anemia.",
    ]
    for t in texts:
        fixed = apply_guardrail(t)
        assert not has_definitive_diagnosis(fixed), f"Guardrail missed: {t!r} → {fixed!r}"


# ── DISCLAIMER always present ───────────────────────────────────────────────

def test_disclaimer_is_non_empty():
    assert len(DISCLAIMER) > 50

def test_disclaimer_mentions_clinician():
    assert "clinician" in DISCLAIMER.lower() or "professional" in DISCLAIMER.lower()
