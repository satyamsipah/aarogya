"""Tests for GET /patients and GET /patients/{id} endpoints."""
from tests.conftest import SAMPLE_BUNDLE
from app.loader import load_bundle


def _seed(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()   # push pending inserts into the transaction


# ---------------------------------------------------------------------------
# GET /patients
# ---------------------------------------------------------------------------

def test_list_patients_empty(client):
    resp = client.get("/patients")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_patients_returns_demographics(client, db_session):
    _seed(db_session)
    resp = client.get("/patients")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    p = data[0]
    assert p["fhir_id"] == "patient-001"
    assert p["family_name"] == "Patel"
    assert p["given_names"] == "Priya A."
    assert p["gender"] == "female"
    assert p["birth_date"] == "1985-07-22"


def test_list_patients_no_raw_in_response(client, db_session):
    """raw FHIR JSON must not leak into the list response."""
    _seed(db_session)
    data = client.get("/patients").json()
    assert "raw" not in data[0]


# ---------------------------------------------------------------------------
# GET /patients/{id}
# ---------------------------------------------------------------------------

def test_get_patient_not_found(client):
    resp = client.get("/patients/does-not-exist")
    assert resp.status_code == 404


def test_get_patient_detail(client, db_session):
    _seed(db_session)
    resp = client.get("/patients/patient-001")
    assert resp.status_code == 200
    body = resp.json()

    # Demographics
    assert body["patient"]["family_name"] == "Patel"

    # Observations (2 from the bundle)
    assert len(body["observations"]) == 2
    codes = {o["code_display"] for o in body["observations"]}
    assert "Cholesterol [Mass/volume] in Serum or Plasma" in codes
    assert "Heart rate" in codes

    # Medications (1)
    assert len(body["medications"]) == 1
    assert "Lisinopril" in body["medications"][0]["medication_display"]

    # Diagnostic reports (1)
    assert len(body["reports"]) == 1
    assert body["reports"][0]["conclusion"] == "Total cholesterol within normal range."


def test_get_patient_no_raw_in_response(client, db_session):
    """raw FHIR JSON must not leak into the detail response."""
    _seed(db_session)
    body = client.get("/patients/patient-001").json()
    assert "raw" not in body["patient"]
    for o in body["observations"]:
        assert "raw" not in o


def test_observations_sorted_newest_first(client, db_session):
    _seed(db_session)
    obs = client.get("/patients/patient-001").json()["observations"]
    dates = [o["effective_dt"] for o in obs]
    assert dates == sorted(dates, reverse=True)
