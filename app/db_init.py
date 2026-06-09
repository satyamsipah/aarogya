"""
Run once (after `docker compose up -d`) to create all tables.
    python -m app.db_init
"""
from app.database import engine, Base
import app.models  # registers all models with Base.metadata


def init_db() -> None:
    Base.metadata.create_all(engine)
    print("Tables created (or already exist).")


if __name__ == "__main__":
    init_db()
