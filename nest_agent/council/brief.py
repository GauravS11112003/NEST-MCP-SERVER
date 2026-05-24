"""Assemble consult envelope injected before the single synthesis LLM call."""

from __future__ import annotations

from typing import Any

from .binder import bind_dyad
from .engine import run_council
from .router import detect_consult_intent


def build_consult_envelope(user_message: str, fhir_data: dict[str, Any] | None) -> dict[str, Any]:
    intent = detect_consult_intent(user_message)
    dyad = bind_dyad(user_message, fhir_data)
    council = run_council(dyad)
    return {
        "consult_intent": intent,
        "dyad": dyad,
        "council": council,
        "synthesis_rules": {
            "llm_calls": 1,
            "instruction": (
                "Use ONLY facts from dyad and council lanes. Do not invent vitals, scores, "
                "medications, or source IDs. Every recommendation must cite a source_id from "
                "the council brief."
            ),
        },
    }
