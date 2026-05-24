"""Inject pre-computed council brief into A2A message/send payloads."""

from __future__ import annotations

import json
import logging
from typing import Any

from nest_agent.council import build_consult_envelope

logger = logging.getLogger(__name__)

_BRIEF_OPEN = "\n\n<!-- NEST_COUNCIL_BRIEF\n"
_BRIEF_CLOSE = "\n/NEST_COUNCIL_BRIEF -->\n"


def inject_council_brief(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Append NEST_COUNCIL_BRIEF to the user message text.

    Returns (mutated_payload, changed).
    """
    if not isinstance(payload, dict) or payload.get("method") != "message/send":
        return payload, False

    params = payload.get("params")
    if not isinstance(params, dict):
        return payload, False

    message = params.get("message")
    if not isinstance(message, dict):
        return payload, False

    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        return payload, False

    user_text = _parts_text(parts)
    fhir_data = _fhir_from_message(message, params)
    envelope = build_consult_envelope(user_text, fhir_data)
    brief_json = json.dumps(envelope, ensure_ascii=False, indent=2, default=str)
    injection = _BRIEF_OPEN + brief_json + _BRIEF_CLOSE

    if _BRIEF_OPEN in user_text:
        return payload, False

    appended = False
    for part in reversed(parts):
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            part["text"] = part["text"] + injection
            appended = True
            break

    if not appended:
        parts.append({"text": injection.lstrip()})

    logger.info(
        "nest_council_brief_injected intent=%s binding=%s score=%s",
        envelope.get("consult_intent"),
        (envelope.get("dyad") or {}).get("binding_source"),
        ((envelope.get("council") or {}).get("transition_score") or {}).get("score"),
    )
    return payload, True


def _parts_text(parts: list) -> str:
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts)


def _fhir_from_message(message: dict, params: dict) -> dict[str, Any] | None:
    from shared.fhir_hook import extract_fhir_from_payload

    _, fhir_data = extract_fhir_from_payload({"params": params})
    if fhir_data:
        return fhir_data
    _, fhir_data = extract_fhir_from_payload({"params": {"message": message}})
    return fhir_data
