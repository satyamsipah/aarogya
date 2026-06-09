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

# 5. Create database tables (run once)
python -m app.db_init

# 6. Run the API
uvicorn app.main:app --reload
# UI → http://localhost:8000/ui/
```

## Generating synthetic patient data (Synthea)

Aarogya ingests [Synthea](https://github.com/synthetichealth/synthea) FHIR R4 JSON bundles.

### Prerequisites
- Java 11+ (`java -version`)
- ~500 MB disk space

### Generate data

```bash
# Download the Synthea standalone JAR (one-time)
curl -L https://github.com/synthetichealth/synthea/releases/latest/download/synthea-with-dependencies.jar \
     -o synthea.jar

# Generate 10 synthetic patients (FHIR R4 bundles)
java -jar synthea.jar \
     -p 10 \
     --exporter.fhir.export=true \
     --exporter.baseDirectory=./synthea_output

# Copy the FHIR bundles into the data directory
cp synthea_output/fhir/*.json data/synthea/
```

Synthea writes one `*.json` transaction bundle per patient.
Each bundle contains Patient, Observation, MedicationRequest, DiagnosticReport, Encounter, and other FHIR R4 resources.

### Load data into Aarogya

```bash
# With venv active and Postgres running:
python -m app.loader
```

The loader is idempotent — re-running it will upsert without duplicates.

## Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + DB connectivity check |
| GET | `/patients` | List all patients (demographics) |
| GET | `/patients/{id}` | Full record: demographics, medications, observations, reports |
| GET | `/ui/` | Patient profile browser (HTML) |

## Safety
- No definitive diagnoses are generated.
- All clinical suggestions are decision-support only, grounded in citations.
- Secrets are loaded from environment variables — never committed.

## Tech stack
- **API**: FastAPI + Uvicorn
- **DB**: PostgreSQL 16 + pgvector
- **ORM**: SQLAlchemy 2.x
- **Clinical schema**: FHIR R4 (Patient, Observation, MedicationRequest, DiagnosticReport)
- **Synthetic data**: Synthea

## Running tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database — no running Postgres required.
