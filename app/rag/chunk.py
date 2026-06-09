"""
Sentence-aware text chunker.

Splits text at sentence boundaries, targeting max_chars per chunk with
overlap_chars of carry-over context between consecutive chunks.
"""
from __future__ import annotations
import re


def split_sentences(text: str) -> list[str]:
    """Rough sentence splitter — good enough for clinical abstracts."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p]


def chunk_text(text: str, max_chars: int = 1800, overlap_chars: int = 200) -> list[str]:
    """
    Returns a list of non-empty chunks each ≤ max_chars.
    Consecutive chunks share up to overlap_chars of text for context continuity.
    """
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent) + 1  # +1 for the space
        if current_len + sent_len > max_chars and current:
            chunk = ' '.join(current)
            chunks.append(chunk)
            # carry overlap: keep trailing sentences that fit in overlap_chars
            overlap: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) + 1 > overlap_chars:
                    break
                overlap.insert(0, s)
                overlap_len += len(s) + 1
            current = overlap
            current_len = overlap_len

        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(' '.join(current))

    return [c.strip() for c in chunks if len(c.strip()) > 80]
