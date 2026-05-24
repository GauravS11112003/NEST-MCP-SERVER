"""
NEST orchestrator — single-call synthesizer.

Clinical facts are pre-computed in Python (see nest_agent.council) and injected
into each consult as NEST_COUNCIL_BRIEF before this agent runs. This agent makes
exactly ONE Gemini call to render the TUI artifact — no sub-agent LLM hops.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .council.prompt import SYNTHESIZER_INSTRUCTION

_model = LiteLlm(model=os.getenv("NEST_ORCHESTRATOR_MODEL", "gemini/gemini-2.5-flash"))

root_agent = Agent(
    name="nest_council",
    model=_model,
    description=(
        "NEST — Newborn & Maternal Safe Transition. Converts postpartum consults "
        "into structured, evidence-backed TUI reports for the mother-infant dyad."
    ),
    instruction=SYNTHESIZER_INSTRUCTION,
    tools=[],
)
