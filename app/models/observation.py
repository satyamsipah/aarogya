from sqlalchemy import Column, String, Float, ForeignKey, JSON
from app.database import Base


class Observation(Base):
    __tablename__ = "observations"

    fhir_id = Column(String, primary_key=True)
    patient_fhir_id = Column(String, ForeignKey("patients.fhir_id"), nullable=False, index=True)
    status = Column(String)
    category = Column(String)       # e.g. "laboratory", "vital-signs"
    code_system = Column(String)    # e.g. "http://loinc.org"
    code_value = Column(String)     # e.g. "2093-3"
    code_display = Column(String)
    effective_dt = Column(String)   # ISO-8601 string from FHIR effectiveDateTime
    value_quantity = Column(Float)
    value_unit = Column(String)
    value_string = Column(String)   # used when result is non-numeric
    raw = Column(JSON, nullable=False)
