from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from selection_policy import (
    NEAR_MISS_LIMIT,
    NEAR_MISS_MIN_OBJECTIVE_SCORE,
    NEAR_MISS_MIN_REGULATORY_OBJECTIVE_SCORE,
    NEAR_MISS_MIN_STORY_SCORE,
    STORY_OBJECTIVE_MIN_SCORES,
    STORY_STRONG_OBJECTIVE_SCORE,
    STORY_STRONG_SCORE,
    TARGET_THEME_KEYS,
)
from signal_quality import classify_mapping_materiality


OBJECTIVE_MIN_SCORES = STORY_OBJECTIVE_MIN_SCORES
NEAR_MISS_BLOCKED_SUMMARY_PHRASES = {
    "integration leads should",
    "health it owners should",
    "backlog review",
    "fhir/api dependencies",
    "fhir api dependencies",
    "operator implication",
    "operator planning",
    "roadmap time",
    "why it matters",
}
SKIPPED_NEWS_LIMIT = 3
SKIPPED_NEWS_BLOCKED_SUMMARY_PHRASES = {
    *NEAR_MISS_BLOCKED_SUMMARY_PHRASES,
    "did not clear the bar",
    "skipped because",
    "do not assign roadmap",
    "soft announcement",
}
SIGNAL_QUALITY_RANK = {"weak": 0, "medium": 1, "strong": 2}


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def story_low_signal_announcement(story: Dict[str, Any]) -> bool:
    if "low_signal_announcement" in story:
        return bool(story.get("low_signal_announcement"))
    return bool(classify_mapping_materiality(story)["low_signal_announcement"])


def story_signal_quality_label(story: Dict[str, Any]) -> str:
    explicit = str(story.get("signal_quality", "") or "").lower()
    if explicit in SIGNAL_QUALITY_RANK:
        return explicit
    return str(classify_mapping_materiality(story)["signal_quality"])


def max_story_objective_score(story: Dict[str, Any]) -> float:
    objective_scores = story.get("objective_scores", {}) or {}
    return max((float(value or 0.0) for value in objective_scores.values()), default=0.0)


def story_is_recall_enforcement(story: Dict[str, Any]) -> bool:
    if str(story.get("category", "") or "") != "Regulatory":
        return False
    if str(story.get("topic_key", "") or "") == "recall_enforcement":
        return True
    return str(story.get("subcategory", "") or "") in {
        "recall",
        "enforcement",
        "safety_alert",
    }


def recall_enforcement_has_primary_slot_signal(story: Dict[str, Any]) -> bool:
    operator_relevance = str(story.get("operator_relevance", "low") or "low")
    workflow_wedges = [str(value) for value in story.get("workflow_wedges", []) or []]
    matched_themes = {str(value) for value in story.get("matched_themes", []) or []}
    support_count = int(story.get("supporting_item_count", 0) or 0)

    return (
        operator_relevance in {"high", "medium"}
        or bool(workflow_wedges)
        or support_count >= 2
        or bool(story.get("watchlist_matches"))
        or bool(matched_themes & TARGET_THEME_KEYS)
    )


def story_has_target_fit(story: Dict[str, Any]) -> bool:
    category = str(story.get("category", "") or "")
    operator_relevance = str(story.get("operator_relevance", "low") or "low")
    actionability = str(story.get("near_term_actionability", "low") or "low")
    workflow_wedges = [str(value) for value in story.get("workflow_wedges", []) or []]
    matched_themes = {str(value) for value in story.get("matched_themes", []) or []}
    has_watchlist_match = bool(story.get("watchlist_matches"))

    if bool(story.get("docs_only_repo")):
        return False
    if story_low_signal_announcement(story) or story_signal_quality_label(story) == "weak":
        return False

    if category == "Regulatory":
        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        return (
            regulatory_score >= OBJECTIVE_MIN_SCORES["regulatory"]
            or bool(workflow_wedges)
            or operator_relevance in {"high", "medium"}
        )

    if category == "Repo":
        if bool(story.get("is_generic_devtool")) and not bool(story.get("generic_repo_cap_exempt")):
            return has_watchlist_match or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_story_objective_score(story) >= 7.2
                and actionability != "low"
            )
        return (
            has_watchlist_match
            or bool(workflow_wedges)
            or operator_relevance == "high"
            or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_story_objective_score(story) >= STORY_STRONG_OBJECTIVE_SCORE
                and actionability != "low"
            )
        )

    if category == "News":
        return (
            operator_relevance in {"high", "medium"}
            and (
                bool(workflow_wedges)
                or actionability in {"high", "medium"}
                or bool(matched_themes & TARGET_THEME_KEYS)
            )
        )

    return False


def story_surface_worthiness(story: Dict[str, Any]) -> Tuple[bool, str]:
    if story_low_signal_announcement(story):
        return False, "soft announcement lacks concrete operator materiality."
    if story_signal_quality_label(story) == "weak":
        return False, "story signal quality is weak."
    if not story_has_target_fit(story):
        return False, "target-fit check failed."
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return False, "reliability is low without corroborating support."

    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    actionability = str(story.get("near_term_actionability", "low") or "low")
    support_count = int(story.get("supporting_item_count", 0) or 0)

    if story.get("category") == "Regulatory":
        if story_is_recall_enforcement(story) and not recall_enforcement_has_primary_slot_signal(story):
            return False, "recall/enforcement story lacks a stronger primary-slot usefulness signal."

        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        if story_score >= 18.0:
            return True, "regulatory story score threshold passed."
        if regulatory_score >= OBJECTIVE_MIN_SCORES["regulatory"]:
            return True, "regulatory objective threshold passed."
        if support_count >= 2:
            return True, "regulatory story has corroborating support."
        return False, "regulatory story score/objective/support thresholds were not strong enough."

    if story_score >= STORY_STRONG_SCORE:
        return True, "story score threshold passed."
    if max_objective >= STORY_STRONG_OBJECTIVE_SCORE and actionability != "low":
        return True, "strong objective threshold passed."
    if support_count >= 2 and actionability in {"high", "medium"}:
        return True, "story has corroborating support and actionability."
    return False, "story score/objective thresholds were not strong enough."


def story_surface_worthiness_reason(story: Dict[str, Any]) -> str:
    return story_surface_worthiness(story)[1]


def story_is_surface_worthy(story: Dict[str, Any]) -> bool:
    return story_surface_worthiness(story)[0]


def compact_one_line(value: object, *, max_length: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""

    sentence_match = re.search(r"^(.+?[.!?])(?:\s|$)", text)
    line = sentence_match.group(1).strip() if sentence_match else text
    if len(line) > max_length:
        trimmed = line[: max_length - 1].rsplit(" ", 1)[0].strip()
        line = f"{trimmed}." if trimmed else line[:max_length].strip()
    if line and line[-1] not in ".!?":
        line = f"{line}."
    return line


def near_miss_summary_is_clean(value: str) -> bool:
    normalized = normalize_text(value)
    if len(normalized.split()) < 5:
        return False
    if any(phrase in normalized for phrase in NEAR_MISS_BLOCKED_SUMMARY_PHRASES):
        return False
    if " should " in f" {normalized} ":
        return False
    return True


def near_miss_summary_for_story(story: Dict[str, Any]) -> str:
    lead_item = story.get("_lead_item", {}) if isinstance(story.get("_lead_item"), dict) else {}
    raw_item = lead_item.get("_item", {}) if isinstance(lead_item.get("_item"), dict) else {}
    candidates = [
        story.get("summary", ""),
        lead_item.get("summary", ""),
        raw_item.get("summary", ""),
        story.get("evidence", ""),
        raw_item.get("raw_text", ""),
    ]
    for candidate in candidates:
        line = compact_one_line(candidate)
        if line and near_miss_summary_is_clean(line):
            return line
    return ""


def user_facing_skip_reason_for_story(story: Dict[str, Any], rejection_reason: str) -> str:
    reason = str(rejection_reason or "").lower()
    if story_low_signal_announcement(story) or "soft announcement" in reason:
        return "it was still an early announcement without concrete deployment or workflow evidence"
    if story_signal_quality_label(story) == "weak" or "signal quality is weak" in reason:
        return "the signal was still too weak"
    if "regulatory story score" in reason:
        return "regulatory usefulness stayed below the operator-grade threshold"
    if "recall/enforcement" in reason:
        return "the recall/enforcement angle lacked a stronger workflow signal"
    if "corroborating support" in reason or "reliability is low" in reason:
        return "source support was too thin"
    if "target-fit" in reason:
        return "operator fit was too indirect"
    if "score/objective" in reason or "threshold" in reason:
        return "score and objective evidence stayed below the operator-grade threshold"
    return "evidence was not strong enough for the main digest"


def near_miss_reason_for_story(story: Dict[str, Any], rejection_reason: str) -> str:
    return user_facing_skip_reason_for_story(story, rejection_reason)


def story_has_near_miss_floor(story: Dict[str, Any]) -> bool:
    if story_low_signal_announcement(story):
        return False
    if story_signal_quality_label(story) == "weak":
        return False
    if not story_has_target_fit(story):
        return False
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return False

    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    support_count = int(story.get("supporting_item_count", 0) or 0)
    actionability = str(story.get("near_term_actionability", "low") or "low")

    if story.get("category") == "Regulatory":
        regulatory_score = float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
        return (
            story_score >= 12.0
            or regulatory_score >= NEAR_MISS_MIN_REGULATORY_OBJECTIVE_SCORE
            or support_count >= 2
        )

    return (
        story_score >= NEAR_MISS_MIN_STORY_SCORE
        or max_objective >= NEAR_MISS_MIN_OBJECTIVE_SCORE
        or (support_count >= 2 and actionability in {"high", "medium"})
    )


def near_miss_rank(story: Dict[str, Any]) -> Tuple[float, float, int, int, str]:
    story_score = float(story.get("story_score", 0.0) or 0.0)
    max_objective = max_story_objective_score(story)
    support_count = int(story.get("supporting_item_count", 0) or 0)
    reliability_score = int(story.get("reliability_score", 0) or 0)
    if story.get("category") == "Regulatory":
        score_ratio = story_score / 18.0
        objective_ratio = (
            float((story.get("objective_scores", {}) or {}).get("regulatory", 0.0) or 0.0)
            / OBJECTIVE_MIN_SCORES["regulatory"]
        )
    else:
        score_ratio = story_score / STORY_STRONG_SCORE
        objective_ratio = max_objective / STORY_STRONG_OBJECTIVE_SCORE
    return (
        max(score_ratio, objective_ratio) + min(support_count, 2) * 0.05,
        story_score,
        reliability_score,
        support_count,
        str(story.get("cluster_title", "") or ""),
    )


def build_near_miss_items(
    stories: List[Dict[str, Any]],
    *,
    selected_stories: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    selected_story_ids = {
        str(story.get("story_id", "") or "")
        for story in selected_stories
        if str(story.get("story_id", "") or "").strip()
    }
    candidates: List[Tuple[Tuple[float, float, int, int, str], Dict[str, Any]]] = []
    for story in stories:
        story_id = str(story.get("story_id", "") or "")
        if story_id in selected_story_ids:
            continue

        surface_worthy, rejection_reason = story_surface_worthiness(story)
        if surface_worthy or not story_has_near_miss_floor(story):
            continue

        summary = near_miss_summary_for_story(story)
        if not summary:
            continue

        candidates.append(
            (
                near_miss_rank(story),
                {
                    "story_id": story_id,
                    "title": str(story.get("cluster_title", "") or story.get("title", "") or "Untitled story"),
                    "source": str(story.get("source", "") or ""),
                    "summary": summary,
                    "miss_reason": near_miss_reason_for_story(story, rejection_reason),
                    "rejection_reason": rejection_reason,
                    "story_score": round(float(story.get("story_score", 0.0) or 0.0), 2),
                    "max_objective_score": round(max_story_objective_score(story), 2),
                    "signal_quality": story_signal_quality_label(story),
                },
            )
        )

    ranked = sorted(
        candidates,
        key=lambda entry: (entry[0], entry[1]["title"]),
        reverse=True,
    )
    return [item for _rank, item in ranked[:NEAR_MISS_LIMIT]]


def skipped_news_summary_is_clean(value: str) -> bool:
    normalized = normalize_text(value)
    if len(normalized.split()) < 5:
        return False
    if any(phrase in normalized for phrase in SKIPPED_NEWS_BLOCKED_SUMMARY_PHRASES):
        return False
    return True


def skipped_news_summary_for_story(story: Dict[str, Any]) -> str:
    lead_item = story.get("_lead_item", {}) if isinstance(story.get("_lead_item"), dict) else {}
    raw_item = lead_item.get("_item", {}) if isinstance(lead_item.get("_item"), dict) else {}
    candidates = [
        story.get("summary", ""),
        lead_item.get("summary", ""),
        raw_item.get("summary", ""),
        raw_item.get("raw_text", ""),
    ]
    for candidate in candidates:
        line = compact_one_line(candidate)
        if line and skipped_news_summary_is_clean(line):
            return line
    return ""


def skipped_news_rank(story: Dict[str, Any]) -> Tuple[float, float, int, str, str]:
    lead_item = story.get("_lead_item", {}) if isinstance(story.get("_lead_item"), dict) else {}
    return (
        float(story.get("story_score", 0.0) or 0.0),
        max_story_objective_score(story),
        int(story.get("reliability_score", 0) or 0),
        str(lead_item.get("published_at", "") or ""),
        str(story.get("cluster_title", "") or ""),
    )


def build_skipped_news_items(
    stories: List[Dict[str, Any]],
    *,
    selected_stories: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    selected_story_ids = {
        str(story.get("story_id", "") or "")
        for story in selected_stories
        if str(story.get("story_id", "") or "").strip()
    }
    candidates: List[Tuple[Tuple[float, float, int, str, str], Dict[str, Any]]] = []
    for story in stories:
        story_id = str(story.get("story_id", "") or "")
        if story_id in selected_story_ids or str(story.get("category", "") or "") != "News":
            continue

        surface_worthy, rejection_reason = story_surface_worthiness(story)
        if surface_worthy:
            continue

        summary = skipped_news_summary_for_story(story)
        if not summary:
            continue

        candidates.append(
            (
                skipped_news_rank(story),
                {
                    "story_id": story_id,
                    "title": str(story.get("cluster_title", "") or story.get("title", "") or "Untitled story"),
                    "source": str(story.get("source", "") or ""),
                    "summary": summary,
                    "skip_reason": user_facing_skip_reason_for_story(story, rejection_reason),
                    "rejection_reason": rejection_reason,
                    "story_score": round(float(story.get("story_score", 0.0) or 0.0), 2),
                    "max_objective_score": round(max_story_objective_score(story), 2),
                    "signal_quality": story_signal_quality_label(story),
                },
            )
        )

    ranked = sorted(
        candidates,
        key=lambda entry: (entry[0], entry[1]["title"]),
        reverse=True,
    )
    return [item for _rank, item in ranked[:SKIPPED_NEWS_LIMIT]]
