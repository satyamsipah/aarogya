from sqlalchemy import Column, String, ForeignKey, JSON
from app.database import Base


class DiagnosticReport(Base):
    __tablename__ = "diagnostic_reports"

    fhir_id = Column(String, primary_key=True)
    patient_fhir_id = Column(String, ForeignKey("patients.fhir_id"), nullable=False, index=True)
    status = Column(String)         # registered | partial | final | amended
    code_value = Column(String)
    code_display = Column(String)
    effective_dt = Column(String)
    conclusion = Column(String)
    raw = Column(JSON, nullable=False)
