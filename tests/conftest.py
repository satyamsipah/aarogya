"""
Shared fixtures for all tests.

Uses an in-memory SQLite database — no running Postgres required.

StaticPool forces all connections from the engine to reuse one underlying
SQLite connection, which is necessary because SQLite ':memory:' databases
are per-connection; without this, create_all() and test sessions would
each see a different (empty) database.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_BUNDLE = FIXTURE_DIR / "sample_bundle.json"


@pytest.fixture
def db_session():
    """
    Fresh in-memory SQLite database + session per test.
    StaticPool ensures create_all() and the session share the same connection.
    """
    import app.models  # noqa: F401 — registers all models with Base.metadata
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """TestClient with get_db overridden to use the per-test SQLite session."""
    from app.database import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
