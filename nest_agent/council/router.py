"""Keyword intent router — no LLM required."""

from __future__ import annotations


def detect_consult_intent(user_message: str) -> str:
    text = user_message.lower()

    if any(
        token in text
        for token in (
            "vital",
            "wearable",
            "telemetry",
            "owlet",
            "apple watch",
            "bp cuff",
            "vitals stream",
        )
    ):
        return "vitals"

    if any(token in text for token in ("ready", "readiness", "safe to discharge", "discharge?")):
        return "discharge_readiness"

    if any(token in text for token in ("epds", "phq-9", "phq9", "depression", "mental health", "mood")):
        return "mental_health"

    if any(token in text for token in ("bilirubin", "jaundice", "bili", "feeding", "latch", "weight loss")):
        return "jaundice_feeding"

    if any(
        token in text
        for token in ("sdoh", "food insecurity", "transport", "medicaid", "social work", "barrier")
    ):
        return "sdoh"

    if any(token in text for token in ("blood pressure", "hypertension", "preeclampsia", "bp ")):
        return "maternal_hypertension"

    return "full_transition"
