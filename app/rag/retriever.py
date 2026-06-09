"""
Hybrid retriever: dense cosine similarity + BM25 keyword search,
fused with Reciprocal Rank Fusion (RRF).

Dense search uses Python-level cosine similarity over all chunk embeddings
(fine for a KB of hundreds of chunks; switch to pgvector ORDER BY <=> for
larger corpora).

BM25 uses rank-bm25 over tokenised chunk text.

RRF formula:  score(d) = Σ  1 / (k + rank_i(d))
                           i
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.rag.embedder import embed_query


@dataclass
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float          # RRF fusion score
    dense_rank: int | None = None
    bm25_rank: int | None = None


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 1e-8 else 0.0


def _tokenise(text: str) -> list[str]:
    """Simple whitespace + lowercase tokeniser for BM25."""
    return text.lower().split()


# ---------------------------------------------------------------------------
# RRF
# ---------------------------------------------------------------------------

def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """
    Reciprocal Rank Fusion over multiple ranked lists of chunk IDs.
    Returns {chunk_id: rrf_score}.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranked_list in rankings:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return scores


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    db: Session,
    top_k: int = 5,
    embed_fn: Callable[[str], list[float]] = embed_query,
) -> list[RetrievedChunk]:
    """
    Retrieve the top-k most relevant KnowledgeChunks for *query*.

    Args:
        query:    Natural-language clinical question.
        db:       SQLAlchemy session (read-only in this call).
        top_k:    Number of chunks to return.
        embed_fn: Override for the query embedding function (useful in tests).

    Returns:
        List of RetrievedChunk ordered by descending RRF score.
        Empty list if the knowledge base has no embedded chunks.
    """
    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.embedding.isnot(None))
        .all()
    )
    if not chunks:
        return []

    query_emb = embed_fn(query)

    # ── Dense ranking ──────────────────────────────────────────────────────
    dense_scores = [
        (c.id, _cosine_similarity(query_emb, list(c.embedding)))
        for c in chunks
    ]
    dense_scores.sort(key=lambda x: -x[1])
    dense_rank_map = {cid: rank for rank, (cid, _) in enumerate(dense_scores, 1)}
    dense_ranking = [cid for cid, _ in dense_scores]

    # ── BM25 ranking ───────────────────────────────────────────────────────
    corpus = [_tokenise(c.text) for c in chunks]
    bm25 = BM25Okapi(corpus)
    bm25_raw = bm25.get_scores(_tokenise(query))
    bm25_indexed = sorted(
        enumerate(bm25_raw), key=lambda x: -x[1]
    )
    bm25_ranking = [chunks[i].id for i, _ in bm25_indexed]
    bm25_rank_map = {cid: rank for rank, cid in enumerate(bm25_ranking, 1)}

    # ── Reciprocal Rank Fusion ─────────────────────────────────────────────
    rrf_scores = _rrf([dense_ranking, bm25_ranking])

    chunk_map = {c.id: c for c in chunks}
    top_ids = sorted(rrf_scores, key=lambda cid: -rrf_scores[cid])[:top_k]

    return [
        RetrievedChunk(
            chunk=chunk_map[cid],
            score=rrf_scores[cid],
            dense_rank=dense_rank_map.get(cid),
            bm25_rank=bm25_rank_map.get(cid),
        )
        for cid in top_ids
    ]
