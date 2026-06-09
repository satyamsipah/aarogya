"""
POST /ask — grounded clinical Q&A endpoint.

Pipeline:
  1. Scan question for emergency red flags → prepend urgent-care warning if found.
  2. Retrieve top-k chunks from the knowledge base (hybrid dense+BM25+RRF).
  3. If no relevant context found → return no_context response immediately.
  4. Call Gemini Flash with context + question.
  5. Post-process: apply diagnosis guardrail, attach disclaimer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.rag.guardrail import DISCLAIMER, apply_guardrail
from app.rag.llm import ask_llm
from app.rag.redflag import build_urgent_warning, detect_red_flags
from app.rag.retriever import retrieve

router = APIRouter(tags=["rag"])

_NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the knowledge base to answer "
    "your question. Please consult a qualified healthcare professional or "
    "refer to a peer-reviewed clinical resource."
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000,
                          description="Clinical question to answer")


class Citation(BaseModel):
    title: str
    source: str   # medlineplus | pubmed | who
    url: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str          # high | medium | low | no_context
    disclaimer: str
    urgent_warning: str | None = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, db: Session = Depends(get_db)):
    """
    Answer a clinical question grounded in the knowledge base.

    - Every claim is sourced and cited.
    - Output is framed as decision-support, not a diagnosis.
    - Emergency symptoms trigger a prominent urgent-care warning.
    """
    # 1. Red-flag scan (runs even if KB is empty)
    flags = detect_red_flags(req.question)
    urgent_warning = build_urgent_warning(flags)

    # 2. Retrieve context
    hits = retrieve(req.question, db, top_k=5)

    # 3. No-context short-circuit
    if not hits:
        return AskResponse(
            answer=_NO_CONTEXT_ANSWER,
            citations=[],
            confidence="no_context",
            disclaimer=DISCLAIMER,
            urgent_warning=urgent_warning,
        )

    # 4. LLM call
    raw = ask_llm(req.question, [h.chunk for h in hits])

    # 5. Guardrail + disclaimer
    answer = apply_guardrail(raw.get("answer", _NO_CONTEXT_ANSWER))

    citations = [
        Citation(
            title=c.get("title", ""),
            source=c.get("source", ""),
            url=c.get("url", ""),
        )
        for c in raw.get("citations", [])
    ]

    return AskResponse(
        answer=answer,
        citations=citations,
        confidence=raw.get("confidence", "low"),
        disclaimer=DISCLAIMER,
        urgent_warning=urgent_warning,
    )
