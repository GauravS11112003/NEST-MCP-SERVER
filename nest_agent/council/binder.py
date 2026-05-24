"""Bind mother-infant dyad context from FHIR metadata or inline message text."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from nest_agent.tools.dyad import _SARAH_DEMO_PATIENT_IDS, _sarah_demo_defaults

logger = logging.getLogger(__name__)

_FHIR_TIMEOUT = 15.0


def _fhir_get(fhir_url: str, token: str, path: str, params: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"}
    response = httpx.get(
        f"{fhir_url.rstrip('/')}/{path}",
        params=params,
        headers=headers,
        timeout=_FHIR_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _entries(bundle: dict) -> list[dict]:
    return [e.get("resource", e) for e in bundle.get("entry", []) if isinstance(e, dict)]


def bind_dyad(user_message: str, fhir_data: dict[str, Any] | None) -> dict[str, Any]:
    """
    Resolve dyad fields for the council engine.

    Priority: Sarah demo fallback → live FHIR maternal chart → sparse unknown dyad.
    """
    fhir_data = fhir_data or {}
    patient_id = str(fhir_data.get("patientId", ""))
    text = user_message or ""

    demo = _sarah_demo_defaults(patient_id, text)
    if demo:
        return {**demo, "binding_source": "demo_or_sarah_defaults", "mother_patient_id": patient_id}

    fhir_url = str(fhir_data.get("fhirUrl", "")).rstrip("/")
    fhir_token = str(fhir_data.get("fhirToken", ""))
    if fhir_url and fhir_token and patient_id:
        try:
            bound = _bind_from_fhir(fhir_url, fhir_token, patient_id, text)
            if bound:
                return bound
        except Exception as exc:
            logger.warning("council_fhir_bind_failed patient_id=%s error=%s", patient_id, exc)

    return {
        "binding_source": "unbound",
        "mother_name": "Unknown Mother",
        "mother_age": 0,
        "delivery_type": "unknown",
        "delivery_date": "",
        "postpartum_day": 0,
        "mother_conditions": [],
        "mother_medications": [],
        "mother_systolic_bp": 0,
        "mother_diastolic_bp": 0,
        "mother_weight_kg": 0,
        "epds_score": -1,
        "sdoh_concerns": [],
        "infant_name": "Unknown Infant",
        "infant_dob": "",
        "infant_age_days": 0,
        "infant_birth_weight_grams": 0,
        "infant_current_weight_grams": 0,
        "infant_gestational_age_weeks": 0,
        "infant_feeding_method": "unknown",
        "infant_feeding_concerns": [],
        "infant_total_bilirubin": 0,
        "infant_age_at_bili_hours": 0,
        "mother_patient_id": patient_id,
        "binding_warning": (
            "Dyad could not be fully resolved from FHIR. Use only facts present in "
            "NEST_COUNCIL_BRIEF and the user message; do not invent clinical data."
        ),
    }


def _bind_from_fhir(fhir_url: str, fhir_token: str, patient_id: str, text: str) -> dict[str, Any] | None:
    patient = _fhir_get(fhir_url, fhir_token, f"Patient/{patient_id}")
    resources: list[dict[str, Any]] = [patient]
    for resource_type in ("Condition", "MedicationRequest", "Observation"):
        try:
            bundle = _fhir_get(
                fhir_url,
                fhir_token,
                resource_type,
                {"subject": f"Patient/{patient_id}", "_count": "50"},
            )
            resources.extend(_entries(bundle))
        except Exception:
            continue

    demo = _sarah_demo_defaults(patient_id, text + " " + str(resources))
    if demo:
        return {**demo, "binding_source": "fhir_with_demo_enrichment", "mother_patient_id": patient_id}

    if patient_id in _SARAH_DEMO_PATIENT_IDS:
        return None

    name = " ".join(
        filter(
            None,
            [
                (patient.get("name") or [{}])[0].get("given", [""])[0]
                if isinstance((patient.get("name") or [{}])[0].get("given"), list)
                else "",
                (patient.get("name") or [{}])[0].get("family", ""),
            ],
        )
    ).strip() or "Unknown Mother"

    return {
        "binding_source": "fhir_minimal",
        "mother_name": name,
        "mother_age": 0,
        "delivery_type": "unknown",
        "delivery_date": "",
        "postpartum_day": _first_int([r"ppd\s*(\d+)", r"postpartum day\s*(\d+)"], text),
        "mother_conditions": [],
        "mother_medications": [],
        "mother_systolic_bp": 0,
        "mother_diastolic_bp": 0,
        "mother_weight_kg": 0,
        "epds_score": -1,
        "sdoh_concerns": [],
        "infant_name": f"Infant of {name}",
        "infant_dob": "",
        "infant_age_days": _first_int([r"dol\s*(\d+)"], text),
        "infant_birth_weight_grams": 0,
        "infant_current_weight_grams": 0,
        "infant_gestational_age_weeks": 0,
        "infant_feeding_method": "unknown",
        "infant_feeding_concerns": [],
        "infant_total_bilirubin": 0,
        "infant_age_at_bili_hours": 0,
        "mother_patient_id": patient_id,
    }


def _first_int(patterns: list[str], text: str) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return 0
