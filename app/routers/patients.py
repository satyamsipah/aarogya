from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.diagnostic_report import DiagnosticReport
from app.models.medication_request import MedicationRequest
from app.models.observation import Observation
from app.models.patient import Patient
from app.schemas import (
    DiagnosticReportOut,
    MedicationRequestOut,
    ObservationOut,
    PatientDetail,
    PatientSummary,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientSummary])
def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient).order_by(Patient.family_name, Patient.given_names).all()


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    observations = (
        db.query(Observation)
        .filter(Observation.patient_fhir_id == patient_id)
        .order_by(Observation.effective_dt.desc())
        .all()
    )
    medications = (
        db.query(MedicationRequest)
        .filter(MedicationRequest.patient_fhir_id == patient_id)
        .order_by(MedicationRequest.authored_on.desc())
        .all()
    )
    reports = (
        db.query(DiagnosticReport)
        .filter(DiagnosticReport.patient_fhir_id == patient_id)
        .order_by(DiagnosticReport.effective_dt.desc())
        .all()
    )

    return PatientDetail(
        patient=PatientSummary.model_validate(patient),
        observations=[ObservationOut.model_validate(o) for o in observations],
        medications=[MedicationRequestOut.model_validate(m) for m in medications],
        reports=[DiagnosticReportOut.model_validate(r) for r in reports],
    )
