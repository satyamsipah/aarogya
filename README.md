# Aarogya — Clinical Co-Pilot

> **Decision-support tool for clinicians. Not a diagnostic system. All output must be reviewed by a qualified human clinician.**

## Overview
Aarogya is a FHIR R4-native clinical co-pilot that surfaces relevant patient context and evidence-backed suggestions to assist — not replace — clinical judgement.

## Quick start

```bash
# 1. Copy and fill in environment variables
cp .env.example .env

# 2. Start Postgres with pgvector
docker compose up -d

# 3. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the API
uvicorn app.main:app --reload
```

## Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + DB connectivity check |

## Safety
- No definitive diagnoses are generated.
- All clinical suggestions are decision-support only, grounded in citations.
- Secrets are loaded from environment variables — never committed.

## Tech stack
- **API**: FastAPI + Uvicorn
- **DB**: PostgreSQL 16 + pgvector
- **ORM**: SQLAlchemy
- **Clinical schema**: FHIR R4
