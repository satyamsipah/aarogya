"""
Google Generative AI embedding wrapper.

Uses text-embedding-004 (768 dims) with task-type hints so that
query vectors and document vectors are optimised differently.
"""
from __future__ import annotations
import google.generativeai as genai
from app.config import settings

_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        if not settings.GOOGLE_API_KEY:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. "
                "Add it to your .env file to use embedding/LLM features."
            )
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        _configured = True


def embed_document(text: str) -> list[float]:
    """Embed a knowledge-base document chunk."""
    _ensure_configured()
    result = genai.embed_content(
        model=settings.EMBED_MODEL,
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
    )
    return result["embedding"]


def embed_query(text: str) -> list[float]:
    """Embed a user query for retrieval."""
    _ensure_configured()
    result = genai.embed_content(
        model=settings.EMBED_MODEL,
        content=text,
        task_type="RETRIEVAL_QUERY",
    )
    return result["embedding"]


def embed_documents_batch(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Batch-embed document chunks. Processes in batches to respect API limits."""
    _ensure_configured()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = genai.embed_content(
            model=settings.EMBED_MODEL,
            content=batch,
            task_type="RETRIEVAL_DOCUMENT",
        )
        # embed_content returns a list of embeddings when content is a list
        embeddings.extend(result["embedding"])
    return embeddings
