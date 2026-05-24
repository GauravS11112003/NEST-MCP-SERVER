"""Deterministic clinical council + single-LLM synthesis support."""

from .brief import build_consult_envelope
from .router import detect_consult_intent

__all__ = ["build_consult_envelope", "detect_consult_intent"]
