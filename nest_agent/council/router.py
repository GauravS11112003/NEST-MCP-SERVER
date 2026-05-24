"""Keyword intent router — no LLM required.

Priority order matters. More specific / higher-intent signals win over clinical
data that Po injects into every message regardless of the clinician's question.
"""

from __future__ import annotations


def detect_consult_intent(user_message: str) -> str:
    # Use only the LAST line / sentence of the message for intent — that is
    # what the clinician typed. Po prepends clinical context above it.
    text_full = user_message.lower()
    lines = [l.strip() for l in user_message.splitlines() if l.strip()]
    # The clinician's question is usually in the last 1-3 lines
    text_tail = " ".join(lines[-3:]).lower() if lines else text_full

    # ── Tier 1: explicit clinician question phrases (check tail first) ─────
    for text in (text_tail, text_full):
        # Discharge readiness — highest priority explicit clinical question
        if any(
            token in text
            for token in (
                "ready for discharge",
                "safe for discharge",
                "discharge readiness",
                "ready to discharge",
                "is the patient ready",
                "can the patient go home",
                "discharge?",
            )
        ):
            return "discharge_readiness"

        # Vitals — explicit wearable/stream request
        if any(
            token in text
            for token in (
                "vitals for mom and baby",
                "vitals for the mom",
                "vitals stream",
                "check wearables",
                "check vitals",
                "wearable telemetry",
                "owlet",
                "apple watch",
                "bp cuff",
            )
        ):
            return "vitals"

        # Specific focused questions
        if any(token in text for token in ("epds", "phq-9", "phq9", "depression screen", "mental health screen")):
            return "mental_health"

        if any(
            token in text
            for token in (
                "what to do with the baby",
                "baby care",
                "jaundice plan",
                "bilirubin plan",
                "feeding plan",
                "latch",
            )
        ):
            return "jaundice_feeding"

        if any(token in text for token in ("social work", "food insecurity", "transport", "medicaid", "sdoh")):
            return "sdoh"

        if any(
            token in text
            for token in ("bp plan", "hypertension plan", "preeclampsia plan", "blood pressure management")
        ):
            return "maternal_hypertension"

    # ── Tier 2: generic vitals mention (only if no stronger signal) ────────
    if "vital" in text_full and not any(
        token in text_full
        for token in ("ready", "readiness", "discharge", "care", "plan", "what", "transition")
    ):
        return "vitals"

    return "full_transition"
