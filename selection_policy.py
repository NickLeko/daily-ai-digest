from __future__ import annotations

import re
from typing import Any, Dict

from signal_quality import classify_mapping_materiality


ITEM_OBJECTIVE_MIN_SCORES = {
    "career": 5.8,
    "build": 6.0,
    "content": 5.4,
    "regulatory": 6.2,
}

STORY_OBJECTIVE_MIN_SCORES = {
    "career": 5.7,
    "build": 5.9,
    "content": 5.2,
    "regulatory": 6.1,
}

STORY_STRONG_SCORE = 28.0
STORY_STRONG_OBJECTIVE_SCORE = 6.7

DAILY_STORY_LIMIT = 4
DAILY_MIN_STORY_COUNT = 3
DAILY_BACKFILL_MIN_STORY_SCORE = 24.0
DAILY_BACKFILL_MIN_OBJECTIVE_SCORE = 5.8
DAILY_SINGLE_STORY_MIN_STORY_SCORE = 32.0
DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE = 6.4

NEAR_MISS_LIMIT = 3
NEAR_MISS_MIN_STORY_SCORE = 14.0
NEAR_MISS_MIN_OBJECTIVE_SCORE = 5.0
NEAR_MISS_MIN_REGULATORY_OBJECTIVE_SCORE = 5.2

TARGET_THEME_KEYS = {
    "healthcare_ai_pm",
    "healthcare_admin_automation",
    "low_reg_friction_wedges",
    "llm_eval_rag_governance_safety",
}

OBJECTIVE_THRESHOLD_KEYS = ("career", "build", "content", "regulatory")


def compact_policy_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def confidence_label(value: object, *, default: str = "Medium") -> str:
    normalized = compact_policy_text(value).lower()
    if normalized == "high":
        return "High"
    if normalized == "medium":
        return "Medium"
    if normalized == "low":
        return "Low"
    return compact_policy_text(value) or default


def story_signal_quality_for_policy(story: Dict[str, Any]) -> str:
    explicit = compact_policy_text(story.get("signal_quality")).lower()
    if explicit in {"strong", "medium", "weak"}:
        return explicit
    return compact_policy_text(classify_mapping_materiality(story)["signal_quality"]).lower()


def story_is_low_signal_for_policy(story: Dict[str, Any]) -> bool:
    if "low_signal_announcement" in story:
        return bool(story.get("low_signal_announcement"))
    return bool(classify_mapping_materiality(story)["low_signal_announcement"])


def story_has_material_signal_for_policy(story: Dict[str, Any]) -> bool:
    if "material_operator_signal" in story:
        return bool(story.get("material_operator_signal"))
    return bool(classify_mapping_materiality(story)["material_operator_signal"])


def confidence_display_for_story(story: Dict[str, Any]) -> Dict[str, str]:
    original = confidence_label(story.get("confidence") or story.get("reliability_label") or "Medium")
    signal_quality = story_signal_quality_for_policy(story)
    low_signal = story_is_low_signal_for_policy(story)
    display = original
    reason = ""

    if low_signal:
        display = "Low"
        reason = "capped_to_low_for_low_signal_announcement"
    elif signal_quality == "weak":
        display = "Low"
        reason = "capped_to_low_for_weak_signal_quality"
    elif signal_quality == "medium" and original == "High":
        display = "Medium"
        reason = "capped_to_medium_for_medium_signal_quality"

    if display == original:
        reason = ""

    return {
        "confidence_display": display,
        "confidence_override_reason": reason,
    }


def threshold_keys_are_aligned() -> bool:
    expected = set(OBJECTIVE_THRESHOLD_KEYS)
    return (
        set(ITEM_OBJECTIVE_MIN_SCORES) == expected
        and set(STORY_OBJECTIVE_MIN_SCORES) == expected
    )
