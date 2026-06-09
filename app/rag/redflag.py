"""
Red-flag emergency symptom detector.

Scans a question or answer for patterns that indicate potential emergencies.
When triggered, a prominent "seek urgent care" warning is prepended to the
response — complying with the CLAUDE.md safety requirement.
"""
from __future__ import annotations
import re

# Each tuple: (compiled_regex, human_readable_label)
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bchest\s+pain\b", re.I), "chest pain"),
    (re.compile(r"\bshortness\s+of\s+breath\b|\bdifficulty\s+breathing\b|\bcannot?\s+breathe\b", re.I), "difficulty breathing"),
    (re.compile(r"\bstroke\b|\bfacial?\s+droop\b|\barm\s+weakness\b|\bslurred?\s+speech\b|\bsudden\s+numbness\b", re.I), "stroke symptoms (FAST)"),
    (re.compile(r"\bheart\s+attack\b|\bmyocardial\s+infarction\b", re.I), "possible heart attack"),
    (re.compile(r"\bsevere\s+bleed|\buncontrolled\s+bleed", re.I), "severe bleeding"),
    (re.compile(r"\bunconscious\b|\bnot\s+breathing\b|\bno\s+pulse\b|\bcardiac\s+arrest\b", re.I), "unconsciousness / cardiac arrest"),
    (re.compile(r"\bsuicid", re.I), "suicidal ideation"),
    (re.compile(r"\bself[- ]harm\b|\bself[- ]injur", re.I), "self-harm"),
    (re.compile(r"\boverdose\b", re.I), "suspected overdose"),
    (re.compile(r"\banaphylax|\bsevere\s+allergic\s+reaction\b", re.I), "anaphylaxis"),
    (re.compile(r"\bseizure\b|\bconvulsion\b|\bstatus\s+epilepticus\b", re.I), "seizure"),
    (re.compile(r"\bsevere\s+abdominal\s+pain\b|\bacute\s+abdomen\b", re.I), "severe abdominal pain"),
    (re.compile(r"\btemperature\s+(?:of\s+)?(?:40|41|42|104|105|106)\b|hyperthermia|heat\s+stroke", re.I), "dangerously high fever"),
    (re.compile(r"\bsepsis\b|\bseptic\s+shock\b", re.I), "possible sepsis"),
    (re.compile(r"\bspinal\s+cord\s+injur|\bparalysis\b", re.I), "possible spinal cord injury"),
]

_URGENT_TEMPLATE = (
    "⚠️  URGENT CARE WARNING\n"
    "Your question mentions symptom(s) that may indicate a medical emergency: "
    "{flags}.\n"
    "If anyone is currently experiencing these symptoms, call emergency services "
    "(911 in the US, 112 in the EU, 999 in the UK) or go to the nearest emergency "
    "department immediately. Do not rely on this tool in an active emergency.\n"
    "─────────────────────────────────────────────────────────────────────────────\n"
)


def detect_red_flags(text: str) -> list[str]:
    """Return list of matched emergency-symptom labels (empty = no flags)."""
    return [label for pattern, label in _PATTERNS if pattern.search(text)]


def build_urgent_warning(flags: list[str]) -> str | None:
    """Format the urgent warning string, or None if no flags."""
    if not flags:
        return None
    return _URGENT_TEMPLATE.format(flags="; ".join(flags))
