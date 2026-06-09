"""
Gemini Flash LLM client for grounded clinical Q&A.

The system prompt enforces three non-negotiable rules:
  1. Answer ONLY from the provided context chunks (no hallucination).
  2. Never issue a definitive diagnosis — frame all output as
     "information to discuss with your clinician".
  3. If context is insufficient, return confidence = "no_context".

The model is instructed to respond in structured JSON so the endpoint
can parse citations without fragile regex.
"""
from __future__ import annotations

import json
import re

import google.generativeai as genai

from app.config import settings

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are Aarogya, a clinical information assistant for healthcare professionals.

NON-NEGOTIABLE RULES — violating any of these is not permitted:
1. Answer ONLY from the CONTEXT sections below. Do not use your training data.
2. NEVER state a definitive diagnosis. Use phrases like "may suggest", "is consistent with", "discuss with your clinician".
3. If the context is insufficient to answer the question, set confidence to "no_context" and explain you cannot answer from available sources.
4. Every factual claim must be attributable to one of the listed sources.
5. Frame all output as "information to discuss with a qualified clinician, not a substitute for professional medical advice."

CONFIDENCE SCALE:
- "high"       — 3+ concordant sources support the answer
- "medium"     — 1-2 sources support the answer
- "low"        — evidence is weak or tangential
- "no_context" — context does not contain enough information to answer

OUTPUT FORMAT — respond with this exact JSON schema and nothing else:
{
  "answer": "<grounded answer, 2-5 sentences>",
  "citations": [
    {"title": "<source title>", "source": "<medlineplus|pubmed|who>", "url": "<url>"}
  ],
  "confidence": "<high|medium|low|no_context>"
}"""

_USER_TEMPLATE = """CONTEXT:
{context}

QUESTION: {question}

Respond with valid JSON only."""

# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _parse_json_response(raw: str) -> dict:
    """Extract and parse the JSON object from the model response."""
    raw = raw.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        # Fallback: return a no_context shell so the endpoint never 500s
        return {
            "answer": "I was unable to parse a structured response. Please try again.",
            "citations": [],
            "confidence": "no_context",
        }


def _format_context(chunks: list) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[{i}] SOURCE: {chunk.source_title}\n"
            f"    TYPE: {chunk.source_type}\n"
            f"    URL: {chunk.source_url}\n"
            f"    TEXT: {chunk.text}"
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def ask_llm(question: str, context_chunks: list) -> dict:
    """
    Query Gemini Flash with retrieved context chunks.

    Args:
        question:       The user's clinical question.
        context_chunks: List of KnowledgeChunk ORM objects (the retrieved context).

    Returns:
        Dict with keys: answer, citations (list), confidence.
        Never raises — returns a no_context shell on any API error.
    """
    if not settings.GOOGLE_API_KEY:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )

    genai.configure(api_key=settings.GOOGLE_API_KEY)

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,    # low temperature for factual grounding
            max_output_tokens=1024,
        ),
    )

    context_text = _format_context(context_chunks)
    prompt = _USER_TEMPLATE.format(context=context_text, question=question)

    # The system instruction is passed separately so Gemini honours it strongly
    full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"

    try:
        response = model.generate_content(full_prompt)
        return _parse_json_response(response.text)
    except Exception as exc:
        return {
            "answer": f"LLM request failed: {exc}",
            "citations": [],
            "confidence": "no_context",
        }
