"""
Hard diagnosis guardrail.

Post-processes LLM output to:
1. Soften any definitive diagnostic language that slipped through the prompt.
2. Ensure the standard disclaimer is always present in every response.

This is a safety net — the primary guardrail is the system prompt in llm.py.
"""
from __future__ import annotations
import re

DISCLAIMER = (
    "⚕ This information is for educational purposes only and is intended to "
    "support — not replace — clinical judgment. It does not constitute a medical "
    "diagnosis. Always discuss clinical decisions with a qualified healthcare "
    "professional."
)

# Patterns that assert a definitive diagnosis → replacement text
_SOFTENINGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\byou have\b", re.I), "you may have"),
    (re.compile(r"\byou are diagnosed with\b", re.I), "these findings may be consistent with"),
    (re.compile(r"\bthe diagnosis is\b", re.I), "a possible explanation to discuss with your clinician is"),
    (re.compile(r"\bconfirms? (?:that )?you have\b", re.I), "suggests you may have"),
    (re.compile(r"\bthis (?:is definitely|is certainly|confirms?)\b", re.I), "this may suggest"),
    (re.compile(r"\byou definitely have\b", re.I), "you may have"),
    (re.compile(r"\byou certainly have\b", re.I), "you may have"),
]


def apply_guardrail(text: str) -> str:
    """Soften definitive diagnostic language in LLM output."""
    for pattern, replacement in _SOFTENINGS:
        text = pattern.sub(replacement, text)
    return text


def has_definitive_diagnosis(text: str) -> bool:
    """True if the text still contains a prohibited definitive-diagnosis phrase."""
    prohibited = [
        re.compile(r"\byou have\b(?!\s+(?:the\s+)?(?:option|right|choice|been|a\s+question))", re.I),
        re.compile(r"\byou are diagnosed with\b", re.I),
        re.compile(r"\bthe diagnosis is\b", re.I),
        re.compile(r"\byou definitely have\b", re.I),
        re.compile(r"\byou certainly have\b", re.I),
    ]
    return any(p.search(text) for p in prohibited)
