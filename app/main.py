from fastapi import FastAPI
from app.database import check_db_connection
from app.config import settings

app = FastAPI(
    title="Aarogya Clinical Co-Pilot",
    description=(
        "Decision-support API for clinicians. "
        "All output must be reviewed by a qualified human clinician."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["ops"])
def health():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "env": settings.APP_ENV,
        "db": "connected" if db_ok else "unreachable",
    }
