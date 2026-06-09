from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class PatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fhir_id: str
    family_name: str | None = None
    given_names: str | None = None
    gender: str | None = None
    birth_date: str | None = None


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fhir_id: str
    status: str | None = None
    category: str | None = None
    code_display: str | None = None
    effective_dt: str | None = None
    value_quantity: float | None = None
    value_unit: str | None = None
    value_string: str | None = None


class MedicationRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fhir_id: str
    status: str | None = None
    medication_display: str | None = None
    authored_on: str | None = None


class DiagnosticReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fhir_id: str
    status: str | None = None
    code_display: str | None = None
    effective_dt: str | None = None
    conclusion: str | None = None


class PatientDetail(BaseModel):
    patient: PatientSummary
    observations: list[ObservationOut]
    medications: list[MedicationRequestOut]
    reports: list[DiagnosticReportOut]
