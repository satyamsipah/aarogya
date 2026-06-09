from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import check_db_connection
from app.routers import patients

app = FastAPI(
    title="Aarogya Clinical Co-Pilot",
    description=(
        "Decision-support API for clinicians. "
        "All output must be reviewed by a qualified human clinician."
    ),
    version="0.2.0",
)

app.include_router(patients.router)


@app.get("/health", tags=["ops"])
def health():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "env": settings.APP_ENV,
        "db": "connected" if db_ok else "unreachable",
    }


# Serve the patient-profile UI at /ui/
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/ui", StaticFiles(directory=str(_frontend), html=True), name="frontend")
