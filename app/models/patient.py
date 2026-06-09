from sqlalchemy import Column, String, JSON
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    # FHIR resource id is the natural primary key — stable across reloads
    fhir_id = Column(String, primary_key=True)
    family_name = Column(String)
    given_names = Column(String)   # space-joined given name list
    gender = Column(String)
    birth_date = Column(String)    # FHIR date string: YYYY-MM-DD
    raw = Column(JSON, nullable=False)
