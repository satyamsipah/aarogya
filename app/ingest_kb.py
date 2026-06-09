"""
Knowledge base ingestion script.

Fetches open-access clinical content from MedlinePlus (NLM) and PubMed (NCBI),
chunks the text, embeds with Google text-embedding-004, and upserts into the
knowledge_chunks Postgres table.

Usage (with venv active and Postgres + .env configured):
    python -m app.ingest_kb               # ingest all default topics
    python -m app.ingest_kb --dry-run     # fetch + chunk, skip embedding/DB write
"""
from __future__ import annotations

import argparse
import sys
import time
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.knowledge_chunk import KnowledgeChunk
from app.rag.chunk import chunk_text
from app.rag.embedder import embed_documents_batch

# --- Topics to ingest -------------------------------------------------------

TOPICS = [
    "type 2 diabetes",
    "hypertension",
    "asthma",
    "depression",
    "coronary artery disease",
    "pneumonia",
    "iron deficiency anemia",
    "anxiety disorder",
    "stroke",
    "chronic kidney disease",
]

# NCBI rate limit: ≤3 req/s without API key
_NCBI_DELAY = 0.4   # seconds between NCBI requests
_HTTP_TIMEOUT = 20  # seconds

# ---------------------------------------------------------------------------
# MedlinePlus fetcher
# ---------------------------------------------------------------------------

_MEDLINE_SEARCH = "https://wsearch.nlm.nih.gov/ws/query"


def _fetch_medlineplus(topic: str, max_docs: int = 2) -> list[dict]:
    """
    Returns list of {source_id, source_url, source_title, text} from
    MedlinePlus XML search API.
    """
    try:
        resp = httpx.get(
            _MEDLINE_SEARCH,
            params={"db": "healthTopics", "term": topic, "retmax": max_docs},
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [medlineplus] fetch error for '{topic}': {exc}")
        return []

    root = ET.fromstring(resp.text)
    docs = []
    for doc_el in root.findall(".//document"):
        url = doc_el.get("url", "")
        title = ""
        full_summary = ""
        for content in doc_el.findall("content"):
            name = content.get("name", "")
            if name == "title":
                title = (content.text or "").strip()
            elif name == "FullSummary":
                soup = BeautifulSoup(content.text or "", "lxml")
                full_summary = soup.get_text(separator=" ", strip=True)

        if full_summary and url:
            slug = url.rstrip("/").split("/")[-1]
            docs.append(
                {
                    "source_id": f"mlp:{slug}",
                    "source_url": url,
                    "source_title": title or topic.title(),
                    "text": full_summary,
                }
            )
    return docs


# ---------------------------------------------------------------------------
# PubMed fetcher
# ---------------------------------------------------------------------------

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _fetch_pubmed(topic: str, max_results: int = 3) -> list[dict]:
    """
    Returns list of {source_id, source_url, source_title, text} from
    PubMed open-access abstracts via NCBI E-utilities.
    """
    try:
        search_resp = httpx.get(
            _ESEARCH,
            params={
                "db": "pubmed",
                "term": f"{topic}[MeSH Terms] OR {topic}[Title/Abstract]",
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
                "filter": "free full text[filter]",
            },
            timeout=_HTTP_TIMEOUT,
        )
        search_resp.raise_for_status()
        time.sleep(_NCBI_DELAY)
    except Exception as exc:
        print(f"  [pubmed] search error for '{topic}': {exc}")
        return []

    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    try:
        fetch_resp = httpx.get(
            _EFETCH,
            params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"},
            timeout=_HTTP_TIMEOUT,
        )
        fetch_resp.raise_for_status()
        time.sleep(_NCBI_DELAY)
    except Exception as exc:
        print(f"  [pubmed] fetch error for '{topic}': {exc}")
        return []

    root = ET.fromstring(fetch_resp.text)
    docs = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//ArticleId[@IdType='pubmed']")
        pmid = pmid_el.text.strip() if pmid_el is not None else None
        if not pmid:
            continue

        title_el = article.find(".//ArticleTitle")
        title = (title_el.text or "").strip() if title_el is not None else ""

        # Collect all AbstractText segments (structured abstracts have multiple)
        abstract_parts = [
            el.text.strip()
            for el in article.findall(".//AbstractText")
            if el.text
        ]
        abstract = " ".join(abstract_parts).strip()
        if not abstract:
            continue

        docs.append(
            {
                "source_id": f"pmid:{pmid}",
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source_title": title or f"PubMed {pmid}",
                "text": abstract,
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

def _build_chunks(docs: list[dict], source_type: str) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for doc in docs:
        for idx, chunk_text_piece in enumerate(chunk_text(doc["text"])):
            chunk_id = f"{source_type}:{doc['source_id']}:{idx}"
            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    source_type=source_type,
                    source_id=doc["source_id"],
                    source_url=doc["source_url"],
                    source_title=doc["source_title"],
                    chunk_index=idx,
                    text=chunk_text_piece,
                    embedding=None,
                )
            )
    return chunks


def ingest_topic(topic: str, db: Session, dry_run: bool = False) -> int:
    """Fetch, chunk, embed, and upsert one topic. Returns number of chunks upserted."""
    print(f"\n[{topic}]")

    ml_docs = _fetch_medlineplus(topic, max_docs=2)
    print(f"  MedlinePlus: {len(ml_docs)} docs")

    pm_docs = _fetch_pubmed(topic, max_results=3)
    print(f"  PubMed:      {len(pm_docs)} docs")

    chunks = _build_chunks(ml_docs, "medlineplus") + _build_chunks(pm_docs, "pubmed")
    print(f"  Chunks:      {len(chunks)}")

    if not chunks or dry_run:
        return len(chunks)

    # Embed in batch
    texts = [c.text for c in chunks]
    embeddings = embed_documents_batch(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    # Upsert (merge is idempotent on primary key)
    for chunk in chunks:
        db.merge(chunk)
    db.commit()

    return len(chunks)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest clinical knowledge base")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + chunk but skip embed/DB write")
    parser.add_argument("--topics", nargs="+", default=TOPICS, help="Override topic list")
    args = parser.parse_args()

    db = SessionLocal()
    total = 0
    try:
        for topic in args.topics:
            total += ingest_topic(topic, db, dry_run=args.dry_run)
    finally:
        db.close()

    mode = "dry-run" if args.dry_run else "ingested"
    print(f"\nDone — {total} chunks {mode} across {len(args.topics)} topics.")
    sys.exit(0)
