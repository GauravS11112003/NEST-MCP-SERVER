"""Run all five council lanes deterministically — zero LLM calls."""

from __future__ import annotations

import os
import re
from typing import Any

from nest_agent.data.aap_newborn import aap_newborn_visits, bhutani_phototherapy_threshold, feeding_milestone_check, newborn_red_flag_panel
from nest_agent.data.acog_postpartum import acog_postpartum_visits, bp_postpartum_assessment, postpartum_red_flag_panel
from nest_agent.data.lactmed import lactation_safety_lookup
from nest_agent.data.mental_health import edinburgh_score_interpretation
from nest_agent.data.sdoh import sdoh_screen_summary


def _weight_loss_pct(birth_g: float, current_g: float) -> float | None:
    if birth_g > 0 and current_g > 0:
        return round((birth_g - current_g) / birth_g * 100, 2)
    return None


def _medication_names(medications: list[str]) -> list[str]:
    names: list[str] = []
    for med in medications:
        token = med.strip().split()[0].lower() if med.strip() else ""
        token = re.sub(r"[^a-z0-9-]", "", token)
        if token and token not in names:
            names.append(token)
    return names


def _has_hypertensive(conditions: list[str], bp_severity: str) -> bool:
    joined = " ".join(conditions).lower()
    if any(k in joined for k in ("preeclampsia", "eclampsia", "hypertension", "hellp")):
        return True
    return bp_severity in {"URGENT", "EMERGENCY"}


def _has_pph(conditions: list[str]) -> bool:
    joined = " ".join(conditions).lower()
    return any(k in joined for k in ("postpartum hemorrhage", "pph", "retained products"))


def _read_wearable_vitals() -> str:
    file_path = os.path.join(os.path.dirname(__file__), "..", "DEMO_VITALS.md")
    try:
        with open(file_path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        return f"Wearable vitals unavailable: {exc}"


def _count_severities(*sections: dict[str, Any]) -> dict[str, int]:
    counts = {"EMERGENCY": 0, "URGENT": 0, "MONITOR": 0}
    for section in sections:
        for key in ("bp_assessment", "jaundice", "feeding", "epds", "verdicts"):
            payload = section.get(key)
            if isinstance(payload, dict):
                sev = str(payload.get("severity", "")).upper()
                if sev in counts:
                    counts[sev] += 1
            elif isinstance(payload, list):
                for row in payload:
                    if isinstance(row, dict):
                        sev = str(row.get("severity", "")).upper()
                        if sev in counts:
                            counts[sev] += 1
    return counts


def compute_transition_score(dyad: dict[str, Any], council: dict[str, Any]) -> dict[str, Any]:
    score = 100
    lanes = council.get("lanes", {})
    sev = _count_severities(
        lanes.get("maternal_ob", {}),
        lanes.get("pediatrics", {}),
        lanes.get("mental_health", {}),
    )
    score -= 15 * sev["EMERGENCY"]
    score -= 8 * sev["URGENT"]
    score -= 3 * sev["MONITOR"]

    if int(dyad.get("epds_score", -1)) < 0:
        score -= 8

    score = max(0, score)
    if score >= 85:
        label = "READY FOR DISCHARGE"
        emoji = "✅"
    elif score >= 65:
        label = "DISCHARGE WITH GAPS"
        emoji = "⚠️"
    elif score >= 40:
        label = "SIGNIFICANT GAPS — DO NOT DISCHARGE WITHOUT REVIEW"
        emoji = "🚨"
    else:
        label = "CRITICAL — UNSAFE FOR DISCHARGE"
        emoji = "🚨"

    filled = round(score / 100 * 24)
    bar = "█" * filled + "░" * (24 - filled)
    return {
        "score": score,
        "label": label,
        "emoji": emoji,
        "bar": bar,
        "severity_counts": sev,
    }


def run_council(dyad: dict[str, Any]) -> dict[str, Any]:
    sys_bp = float(dyad.get("mother_systolic_bp") or 0)
    dia_bp = float(dyad.get("mother_diastolic_bp") or 0)
    conditions = list(dyad.get("mother_conditions") or [])
    bp = bp_postpartum_assessment(sys_bp, dia_bp) if sys_bp and dia_bp else {
        "severity": "UNKNOWN",
        "label": "BP not available",
        "action": "Obtain BP before discharge planning.",
        "source_id": "ACOG-PB-222",
    }

    htn = _has_hypertensive(conditions, str(bp.get("severity", "")))
    pph = _has_pph(conditions)
    acog_visits = acog_postpartum_visits(
        delivery_date=str(dyad.get("delivery_date") or "2026-05-08"),
        has_hypertensive_disorder=htn,
        has_postpartum_hemorrhage=pph,
    )

    birth_g = float(dyad.get("infant_birth_weight_grams") or 0)
    current_g = float(dyad.get("infant_current_weight_grams") or 0)
    wl_pct = _weight_loss_pct(birth_g, current_g)
    bili = bhutani_phototherapy_threshold(
        age_hours=float(dyad.get("infant_age_at_bili_hours") or 0),
        total_bilirubin_mg_dl=float(dyad.get("infant_total_bilirubin") or 0),
        risk_band="medium",
    ) if dyad.get("infant_total_bilirubin") else {"status": "not_measured"}

    feeding = feeding_milestone_check(
        feeding_method=str(dyad.get("infant_feeding_method") or "unknown"),
        age_days=int(dyad.get("infant_age_days") or 0),
        weight_loss_pct=wl_pct,
        feeding_concerns=list(dyad.get("infant_feeding_concerns") or []),
    )

    aap_visits = aap_newborn_visits(
        infant_age_days=int(dyad.get("infant_age_days") or 0),
        hospital_discharge_day=int(dyad.get("infant_age_days") or 0),
    )

    epds = edinburgh_score_interpretation(
        epds_total=int(dyad.get("epds_score", -1)),
        self_harm_item_present=False,
    )

    lactation_rows = []
    for med_name in _medication_names(list(dyad.get("mother_medications") or [])):
        entry = lactation_safety_lookup(med_name)
        lactation_rows.append(entry or {"medication": med_name, "status": "not_in_curated_subset"})

    sdoh = sdoh_screen_summary(concerns=list(dyad.get("sdoh_concerns") or []))

    council = {
        "lanes": {
            "maternal_ob": {
                "bp_assessment": bp,
                "acog_visits": acog_visits,
                "postpartum_red_flags": postpartum_red_flag_panel(),
                "verdicts": [
                    {
                        "topic": "Postpartum BP",
                        "verdict": "🛑 EMERGENCY" if bp.get("severity") == "EMERGENCY" else "⚠️ URGENT",
                        "reason": bp.get("action", bp.get("label", "")),
                        "source": bp.get("source_id", "ACOG-PB-222"),
                    }
                ],
            },
            "pediatrics": {
                "weight_loss_pct": wl_pct,
                "jaundice": bili,
                "feeding": feeding,
                "aap_visits": aap_visits,
                "newborn_red_flags": newborn_red_flag_panel(),
            },
            "lactation": {"medication_reviews": lactation_rows},
            "mental_health": {"epds": epds},
            "social_work": {"sdoh": sdoh},
        },
        "wearable_vitals_markdown": _read_wearable_vitals(),
    }
    council["transition_score"] = compute_transition_score(dyad, council)
    return council
