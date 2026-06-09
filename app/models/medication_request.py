from sqlalchemy import Column, String, ForeignKey, JSON
from app.database import Base


class MedicationRequest(Base):
    __tablename__ = "medication_requests"

    fhir_id = Column(String, primary_key=True)
    patient_fhir_id = Column(String, ForeignKey("patients.fhir_id"), nullable=False, index=True)
    status = Column(String)         # active | completed | stopped | cancelled
    intent = Column(String)         # order | plan | proposal
    medication_code = Column(String)
    medication_display = Column(String)
    authored_on = Column(String)    # FHIR date string
    raw = Column(JSON, nullable=False)
