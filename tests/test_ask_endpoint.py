"""
Tests for POST /ask.

All external calls (retriever, LLM) are mocked so the test suite runs
offline with no API keys required.
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.guardrail import DISCLAIMER

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_chunk(text: str = "Diabetes is managed with metformin.", title: str = "MedlinePlus Diabetes"):
    return SimpleNamespace(
        id="fake-1",
        source_type="medlineplus",
        source_id="fake",
        source_url="https://medlineplus.gov/diabetes.html",
        source_title=title,
        chunk_index=0,
        text=text,
        embedding=[0.1] * 768,
    )

def _fake_retrieved(text: str = "Diabetes is managed with metformin."):
    from app.rag.retriever import RetrievedChunk
    return [RetrievedChunk(chunk=_fake_chunk(text), score=0.9, dense_rank=1, bm25_rank=1)]

def _fake_llm_response(answer: str = "Metformin is the first-line treatment.", confidence: str = "high"):
    return {
        "answer": answer,
        "citations": [
            {
                "title": "MedlinePlus Diabetes",
                "source": "medlineplus",
                "url": "https://medlineplus.gov/diabetes.html",
            }
        ],
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_ask_returns_answer_and_citations():
    with patch("app.routers.ask.retrieve", return_value=_fake_retrieved()), \
         patch("app.routers.ask.ask_llm", return_value=_fake_llm_response()):
        resp = client.post("/ask", json={"question": "How is type 2 diabetes treated?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["source"] == "medlineplus"
    assert body["confidence"] == "high"


def test_ask_disclaimer_always_present():
    """Disclaimer must be in every response regardless of content."""
    with patch("app.routers.ask.retrieve", return_value=_fake_retrieved()), \
         patch("app.routers.ask.ask_llm", return_value=_fake_llm_response()):
        resp = client.post("/ask", json={"question": "What are symptoms of hypertension?"})

    body = resp.json()
    assert body["disclaimer"] == DISCLAIMER
    assert len(body["disclaimer"]) > 50


def test_ask_no_urgent_warning_for_routine_question():
    with patch("app.routers.ask.retrieve", return_value=_fake_retrieved()), \
         patch("app.routers.ask.ask_llm", return_value=_fake_llm_response()):
        resp = client.post("/ask", json={"question": "What is metformin used for?"})

    assert resp.json()["urgent_warning"] is None


# ---------------------------------------------------------------------------
# Red-flag path
# ---------------------------------------------------------------------------

def test_ask_urgent_warning_on_emergency_question():
    with patch("app.routers.ask.retrieve", return_value=_fake_retrieved()), \
         patch("app.routers.ask.ask_llm", return_value=_fake_llm_response()):
        resp = client.post("/ask", json={"question": "Patient has chest pain and cannot breathe"})

    body = resp.json()
    assert body["urgent_warning"] is not None
    assert "chest pain" in body["urgent_warning"].lower() or "URGENT" in body["urgent_warning"]


# ---------------------------------------------------------------------------
# No-context path (empty KB)
# ---------------------------------------------------------------------------

def test_ask_no_context_when_kb_empty():
    with patch("app.routers.ask.retrieve", return_value=[]):
        resp = client.post("/ask", json={"question": "What is the treatment for gout?"})

    body = resp.json()
    assert resp.status_code == 200
    assert body["confidence"] == "no_context"
    assert body["citations"] == []
    assert body["disclaimer"] == DISCLAIMER


def test_ask_no_context_does_not_call_llm():
    """LLM must NOT be called when the knowledge base returns no results."""
    with patch("app.routers.ask.retrieve", return_value=[]) as mock_ret, \
         patch("app.routers.ask.ask_llm") as mock_llm:
        client.post("/ask", json={"question": "Tell me about gout"})
        mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# Guardrail
# ---------------------------------------------------------------------------

def test_ask_guardrail_softens_diagnosis():
    """Even if the LLM sneaks a definitive diagnosis through, guardrail catches it."""
    bad_llm = _fake_llm_response(answer="You have Type 2 Diabetes.")
    with patch("app.routers.ask.retrieve", return_value=_fake_retrieved()), \
         patch("app.routers.ask.ask_llm", return_value=bad_llm):
        resp = client.post("/ask", json={"question": "My blood sugar is 300 mg/dL"})

    from app.rag.guardrail import has_definitive_diagnosis
    assert not has_definitive_diagnosis(resp.json()["answer"])


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_ask_rejects_too_short_question():
    resp = client.post("/ask", json={"question": "hi"})
    assert resp.status_code == 422


def test_ask_rejects_missing_question():
    resp = client.post("/ask", json={})
    assert resp.status_code == 422
