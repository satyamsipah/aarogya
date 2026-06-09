"""
Tests for the hybrid RAG retriever (pure-logic, no DB, no real embeddings).

Uses in-memory fake KnowledgeChunk objects and a deterministic fake embed_fn
to verify that RRF fusion, cosine ranking, and BM25 ranking work correctly.
"""
from __future__ import annotations
import math
from types import SimpleNamespace

import numpy as np
import pytest

from app.rag.retriever import _rrf, _cosine_similarity, retrieve
from app.rag.chunk import chunk_text


# ---------------------------------------------------------------------------
# Unit tests for _rrf and _cosine_similarity
# ---------------------------------------------------------------------------

def test_rrf_scores_sum_correctly():
    # "b" rank-1 in both lists → unambiguously highest score
    scores = _rrf([["b", "a", "c"], ["b", "c", "a"]])
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]
    # "a" rank-2+3; "c" rank-3+2 → equal (both sum to same RRF score)
    assert scores["a"] == scores["c"]

def test_rrf_single_list():
    scores = _rrf([["x", "y", "z"]])
    assert scores["x"] > scores["y"] > scores["z"]

def test_rrf_k_parameter():
    """Higher k flattens scores; k=0 makes rank-1 score = 1.0."""
    scores_k0  = _rrf([["a", "b"]], k=0)
    scores_k60 = _rrf([["a", "b"]], k=60)
    # ratio rank1/rank2 should be larger with k=0
    ratio_k0  = scores_k0["a"]  / scores_k0["b"]
    ratio_k60 = scores_k60["a"] / scores_k60["b"]
    assert ratio_k0 > ratio_k60

def test_cosine_identical_vectors():
    assert math.isclose(_cosine_similarity([1, 0, 0], [1, 0, 0]), 1.0, abs_tol=1e-6)

def test_cosine_orthogonal_vectors():
    assert math.isclose(_cosine_similarity([1, 0, 0], [0, 1, 0]), 0.0, abs_tol=1e-6)

def test_cosine_opposite_vectors():
    assert math.isclose(_cosine_similarity([1, 0], [-1, 0]), -1.0, abs_tol=1e-6)

def test_cosine_zero_vector_safe():
    # Should not raise; returns 0 due to epsilon guard
    result = _cosine_similarity([0, 0, 0], [1, 0, 0])
    assert result == 0.0


# ---------------------------------------------------------------------------
# chunk_text unit tests
# ---------------------------------------------------------------------------

def test_chunk_short_text():
    text = "Short text."
    chunks = chunk_text(text, max_chars=500)
    assert chunks == ["Short text."]

def test_chunk_long_text():
    # 20 identical sentences → must split into multiple chunks
    sentence = "The patient presents with elevated blood pressure. "
    text = sentence * 20
    chunks = chunk_text(text, max_chars=500, overlap_chars=50)
    assert len(chunks) > 1

def test_chunk_empty_string():
    assert chunk_text("") == []

def test_chunk_overlap_provides_context():
    """Last words of chunk N should appear in the start of chunk N+1."""
    sentence = "Hypertension is defined as blood pressure above 130 over 80. "
    text = sentence * 15
    chunks = chunk_text(text, max_chars=400, overlap_chars=100)
    if len(chunks) >= 2:
        # Some overlap words should appear in both chunk 0 and chunk 1
        words_0 = set(chunks[0].lower().split())
        words_1 = set(chunks[1].lower().split())
        assert len(words_0 & words_1) > 0


# ---------------------------------------------------------------------------
# retrieve() integration with fake DB and embed_fn
# ---------------------------------------------------------------------------

def _make_chunk(cid: str, text: str, embedding: list[float]):
    """Create a minimal KnowledgeChunk-like namespace for tests."""
    return SimpleNamespace(
        id=cid,
        source_type="medlineplus",
        source_id=cid,
        source_url=f"https://example.com/{cid}",
        source_title=cid.replace("-", " ").title(),
        chunk_index=0,
        text=text,
        embedding=embedding,
    )

class _FakeDB:
    def __init__(self, chunks):
        self._chunks = chunks

    def query(self, model):
        return self

    def filter(self, *args):
        # Return only chunks with non-None embedding
        return _FakeFilterResult([c for c in self._chunks if c.embedding is not None])

class _FakeFilterResult:
    def __init__(self, items):
        self._items = items
    def all(self):
        return self._items


def _unit_vec(dims: int, hot: int) -> list[float]:
    v = [0.0] * dims
    v[hot] = 1.0
    return v


def test_retrieve_returns_most_similar_first():
    """Chunk whose embedding matches the query vector should rank first."""
    dims = 4
    chunks = [
        _make_chunk("diabetes",     "diabetes treatment insulin glucose", _unit_vec(dims, 0)),
        _make_chunk("hypertension", "blood pressure hypertension amlodipine", _unit_vec(dims, 1)),
        _make_chunk("asthma",       "asthma bronchospasm inhaler albuterol", _unit_vec(dims, 2)),
    ]
    db = _FakeDB(chunks)

    # Query embedding points at "diabetes" direction
    def fake_embed_fn(text: str) -> list[float]:
        return _unit_vec(dims, 0)

    results = retrieve("diabetes insulin", db, top_k=3, embed_fn=fake_embed_fn)
    assert results[0].chunk.id == "diabetes"


def test_retrieve_empty_kb():
    db = _FakeDB([])
    results = retrieve("anything", db, embed_fn=lambda t: [1.0])
    assert results == []


def test_retrieve_no_embedded_chunks():
    """Chunks without embeddings must be filtered out."""
    chunks = [_make_chunk("c1", "some text", None)]
    db = _FakeDB(chunks)
    results = retrieve("query", db, embed_fn=lambda t: [1.0])
    assert results == []


def test_retrieve_top_k_limits_results():
    dims = 3
    chunks = [
        _make_chunk(f"c{i}", f"chunk {i} text", _unit_vec(dims, i % dims))
        for i in range(10)
    ]
    db = _FakeDB(chunks)
    results = retrieve("query", db, top_k=3, embed_fn=lambda t: _unit_vec(dims, 0))
    assert len(results) <= 3


def test_retrieve_result_has_score_and_ranks():
    dims = 2
    chunks = [
        _make_chunk("a", "fever temperature high", _unit_vec(dims, 0)),
        _make_chunk("b", "cough cold viral", _unit_vec(dims, 1)),
    ]
    db = _FakeDB(chunks)
    results = retrieve("high fever", db, top_k=2, embed_fn=lambda t: _unit_vec(dims, 0))
    assert all(r.score > 0 for r in results)
    assert all(r.dense_rank is not None for r in results)
    assert all(r.bm25_rank is not None for r in results)
