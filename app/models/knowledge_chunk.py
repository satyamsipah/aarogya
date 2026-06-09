from sqlalchemy import Column, Integer, String, Text, Index
from pgvector.sqlalchemy import Vector
from app.database import Base
from app.config import settings


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    # Composite natural key: "{source_type}:{source_id}:{chunk_index}"
    id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)    # medlineplus | pubmed
    source_id = Column(String, nullable=False)       # topic slug or PMID
    source_url = Column(String, nullable=False)
    source_title = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBED_DIMS))  # null until embedded

    __table_args__ = (
        Index("ix_kc_source", "source_type", "source_id"),
        # GIN / IVFFlat index added separately via migration once data is loaded:
        # CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    )
