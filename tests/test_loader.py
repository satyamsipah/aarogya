"""Tests for the Synthea FHIR bundle loader."""
from tests.conftest import SAMPLE_BUNDLE
from app.loader import load_bundle, _ref_to_id
from app.models.patient import Patient
from app.models.observation import Observation
from app.models.medication_request import MedicationRequest
from app.models.diagnostic_report import DiagnosticReport


# ---------------------------------------------------------------------------
# Reference resolution helpers
# ---------------------------------------------------------------------------

def test_ref_urn_uuid():
    assert _ref_to_id("urn:uuid:abc-123") == "abc-123"


def test_ref_resource_slash():
    assert _ref_to_id("Patient/xyz-456") == "xyz-456"


def test_ref_bare():
    assert _ref_to_id("bare-id") == "bare-id"


# ---------------------------------------------------------------------------
# Bundle loading
# ---------------------------------------------------------------------------

def test_load_counts(db_session):
    counts = load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    assert counts["Patient"] == 1
    assert counts["Observation"] == 2
    assert counts["MedicationRequest"] == 1
    assert counts["DiagnosticReport"] == 1
    assert counts["skipped"] == 1          # Encounter is not handled


def test_patient_fields(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()   # push pending inserts so get() can find them
    p = db_session.get(Patient, "patient-001")
    assert p is not None
    assert p.family_name == "Patel"
    assert p.given_names == "Priya A."
    assert p.gender == "female"
    assert p.birth_date == "1985-07-22"
    assert p.raw["resourceType"] == "Patient"


def test_observation_fields(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    obs = db_session.get(Observation, "obs-001")
    assert obs is not None
    assert obs.patient_fhir_id == "patient-001"
    assert obs.status == "final"
    assert obs.category == "laboratory"
    assert obs.code_value == "2093-3"
    assert obs.value_quantity == 182.4
    assert obs.value_unit == "mg/dL"


def test_vital_observation(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    obs = db_session.get(Observation, "obs-002")
    assert obs.category == "vital-signs"
    assert obs.value_quantity == 72


def test_medication_request_fields(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    med = db_session.get(MedicationRequest, "medrx-001")
    assert med is not None
    assert med.patient_fhir_id == "patient-001"
    assert med.status == "active"
    assert med.intent == "order"
    assert "Lisinopril" in (med.medication_display or "")
    assert med.authored_on == "2024-01-05"


def test_diagnostic_report_fields(db_session):
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    dr = db_session.get(DiagnosticReport, "dr-001")
    assert dr is not None
    assert dr.patient_fhir_id == "patient-001"
    assert dr.status == "final"
    assert "Lipid" in (dr.code_display or "")
    assert dr.conclusion == "Total cholesterol within normal range."


def test_idempotent_reload(db_session):
    """Loading the same bundle twice must not raise or create duplicates."""
    load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    counts = load_bundle(SAMPLE_BUNDLE, db_session, commit=False)
    db_session.flush()
    assert counts["Patient"] == 1
    total_patients = db_session.query(Patient).count()
    assert total_patients == 1
