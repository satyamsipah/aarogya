"""Tests for the red-flag emergency symptom detector."""
from app.rag.redflag import detect_red_flags, build_urgent_warning


# ── Should trigger ──────────────────────────────────────────────────────────

def test_chest_pain():
    assert "chest pain" in detect_red_flags("patient has chest pain")

def test_shortness_of_breath():
    flags = detect_red_flags("difficulty breathing for two hours")
    assert any("breathing" in f for f in flags)

def test_stroke_keywords():
    flags = detect_red_flags("sudden arm weakness and slurred speech")
    assert any("stroke" in f.lower() for f in flags)

def test_suicidal():
    assert any("suicid" in f for f in detect_red_flags("having suicidal thoughts"))

def test_overdose():
    assert any("overdose" in f for f in detect_red_flags("suspected overdose of acetaminophen"))

def test_seizure():
    flags = detect_red_flags("patient had a seizure lasting 5 minutes")
    assert any("seizure" in f.lower() for f in flags)

def test_anaphylaxis():
    flags = detect_red_flags("anaphylaxis after bee sting")
    assert any("anaphylax" in f.lower() for f in flags)

def test_cardiac_arrest():
    flags = detect_red_flags("patient is unconscious and has no pulse")
    assert any(kw in f.lower() for f in flags for kw in ("cardiac", "conscious"))


# ── Should NOT trigger ──────────────────────────────────────────────────────

def test_mild_headache():
    assert detect_red_flags("I have a mild headache") == []

def test_common_cold():
    assert detect_red_flags("runny nose and sneezing for two days") == []

def test_medication_query():
    assert detect_red_flags("what is the dosage of metformin for type 2 diabetes?") == []


# ── Warning message format ──────────────────────────────────────────────────

def test_urgent_warning_none_when_no_flags():
    assert build_urgent_warning([]) is None

def test_urgent_warning_contains_flags():
    warning = build_urgent_warning(["chest pain", "stroke symptoms"])
    assert warning is not None
    assert "chest pain" in warning
    assert "stroke symptoms" in warning

def test_urgent_warning_mentions_emergency_services():
    warning = build_urgent_warning(["chest pain"])
    assert "emergency" in warning.lower() or "911" in warning
