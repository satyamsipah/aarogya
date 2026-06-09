"""
Synthea FHIR R4 bundle loader.

Supports both Synthea reference formats:
  - urn:uuid:<id>   (transaction bundles — Synthea default)
  - Patient/<id>    (searchset / other bundles)

CLI usage:
    python -m app.loader              # loads all *.json in data/synthea/
    python -m app.loader path/to/bundle.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.observation import Observation
from app.models.medication_request import MedicationRequest
from app.models.diagnostic_report import DiagnosticReport


# ---------------------------------------------------------------------------
# Reference helpers
# ---------------------------------------------------------------------------

def _ref_to_id(reference: str) -> str:
    """Strip urn:uuid: or Resource/ prefix to get the bare FHIR id."""
    if reference.startswith("urn:uuid:"):
        return reference[9:]
    if "/" in reference:
        return reference.rsplit("/", 1)[-1]
    return reference


def _first(lst: list, default=None):
    return lst[0] if lst else default


def _first_coding(codeable_concept: dict) -> dict:
    return _first(codeable_concept.get("coding", []), {})


# ---------------------------------------------------------------------------
# Per-resource parsers
# ---------------------------------------------------------------------------

def _parse_patient(r: dict) -> Optional[Patient]:
    fhir_id = r.get("id")
    if not fhir_id:
        return None

    names = r.get("name", [])
    official = next((n for n in names if n.get("use") == "official"), _first(names, {}))
    family = official.get("family")
    given = " ".join(official.get("given", [])) or None

    return Patient(
        fhir_id=fhir_id,
        family_name=family,
        given_names=given,
        gender=r.get("gender"),
        birth_date=r.get("birthDate"),
        raw=r,
    )


def _parse_observation(r: dict) -> Optional[Observation]:
    fhir_id = r.get("id")
    if not fhir_id:
        return None

    patient_id = _ref_to_id(r.get("subject", {}).get("reference", ""))

    # Category: first coding of first category element
    cat_coding = _first_coding(_first(r.get("category", []), {}))
    category = cat_coding.get("code")

    code_coding = _first_coding(r.get("code", {}))
    code_display = code_coding.get("display") or r.get("code", {}).get("text")

    # Value: numeric quantity, string, or coded concept
    value_qty: Optional[float] = None
    value_unit: Optional[str] = None
    value_str: Optional[str] = None

    if "valueQuantity" in r:
        value_qty = r["valueQuantity"].get("value")
        value_unit = r["valueQuantity"].get("unit")
    elif "valueString" in r:
        value_str = r["valueString"]
    elif "valueCodeableConcept" in r:
        vc = r["valueCodeableConcept"]
        value_str = vc.get("text") or _first_coding(vc).get("display")
    elif "valueBoolean" in r:
        value_str = str(r["valueBoolean"])

    return Observation(
        fhir_id=fhir_id,
        patient_fhir_id=patient_id,
        status=r.get("status"),
        category=category,
        code_system=code_coding.get("system"),
        code_value=code_coding.get("code"),
        code_display=code_display,
        effective_dt=r.get("effectiveDateTime") or r.get("effectivePeriod", {}).get("start"),
        value_quantity=value_qty,
        value_unit=value_unit,
        value_string=value_str,
        raw=r,
    )


def _parse_medication_request(r: dict) -> Optional[MedicationRequest]:
    fhir_id = r.get("id")
    if not fhir_id:
        return None

    patient_id = _ref_to_id(r.get("subject", {}).get("reference", ""))

    med_cc = r.get("medicationCodeableConcept", {})
    med_coding = _first_coding(med_cc)

    return MedicationRequest(
        fhir_id=fhir_id,
        patient_fhir_id=patient_id,
        status=r.get("status"),
        intent=r.get("intent"),
        medication_code=med_coding.get("code"),
        medication_display=med_coding.get("display") or med_cc.get("text"),
        authored_on=r.get("authoredOn"),
        raw=r,
    )


def _parse_diagnostic_report(r: dict) -> Optional[DiagnosticReport]:
    fhir_id = r.get("id")
    if not fhir_id:
        return None

    patient_id = _ref_to_id(r.get("subject", {}).get("reference", ""))
    code_coding = _first_coding(r.get("code", {}))

    return DiagnosticReport(
        fhir_id=fhir_id,
        patient_fhir_id=patient_id,
        status=r.get("status"),
        code_value=code_coding.get("code"),
        code_display=code_coding.get("display") or r.get("code", {}).get("text"),
        effective_dt=r.get("effectiveDateTime") or r.get("effectivePeriod", {}).get("start"),
        conclusion=r.get("conclusion"),
        raw=r,
    )


_PARSERS = {
    "Patient": _parse_patient,
    "Observation": _parse_observation,
    "MedicationRequest": _parse_medication_request,
    "DiagnosticReport": _parse_diagnostic_report,
}

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

LoadResult = dict[str, int]


def load_bundle(path: str | Path, db: Session, commit: bool = True) -> LoadResult:
    """
    Parse a single Synthea FHIR R4 bundle and upsert into *db*.

    Args:
        path:   Path to the bundle JSON file.
        db:     SQLAlchemy session.
        commit: If True (default), commit after processing. Pass False in tests
                to let the caller manage the transaction.

    Returns:
        Dict of {resourceType: count_upserted, "skipped": count_skipped}.
    """
    with open(path) as f:
        bundle = json.load(f)

    counts: LoadResult = {k: 0 for k in _PARSERS} | {"skipped": 0}

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        parser = _PARSERS.get(rtype)
        if parser is None:
            counts["skipped"] += 1
            continue
        obj = parser(resource)
        if obj is None:
            counts["skipped"] += 1
            continue
        db.merge(obj)
        counts[rtype] += 1

    if commit:
        db.commit()

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from app.database import SessionLocal
    import app.models  # noqa: F401 — ensure models are registered

    paths: list[Path] = []
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        data_dir = Path("data/synthea")
        if not data_dir.exists():
            print(f"ERROR: {data_dir} not found. Create it and place Synthea bundles inside.")
            sys.exit(1)
        paths = sorted(data_dir.glob("*.json"))

    if not paths:
        print("No JSON bundles found.")
        sys.exit(1)

    db = SessionLocal()
    try:
        total: LoadResult = {k: 0 for k in _PARSERS} | {"skipped": 0}
        for p in paths:
            result = load_bundle(p, db)
            print(f"  {p.name}: {result}")
            for k in total:
                total[k] += result.get(k, 0)
        print(f"\nTotal: {total}")
    finally:
        db.close()
