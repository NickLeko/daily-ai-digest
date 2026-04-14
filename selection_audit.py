from __future__ import annotations

import json
from typing import Any, Dict, List

from formatter import (
    DAILY_STORY_LIMIT,
    select_daily_stories,
    stories_are_render_duplicates,
    story_id_for_render,
)
from operator_brief import (
    max_story_objective_score,
    story_has_target_fit,
    story_is_surface_worthy,
)
from state import local_now


SELECTION_AUDIT_FILE_PATH = "latest_selection_audit.json"


def rounded_scores(scores: Dict[str, Any] | None) -> Dict[str, float]:
    return {
        str(key): round(float(value or 0.0), 2)
        for key, value in (scores or {}).items()
    }


def score_summary(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "priority_score": round(float(entry.get("priority_score", 0.0) or 0.0), 2),
        "story_score": round(float(entry.get("story_score", entry.get("priority_score", 0.0)) or 0.0), 2),
        "max_objective_score": round(max_story_objective_score(entry), 2),
        "objective_scores": rounded_scores(entry.get("objective_scores")),
        "score_dimensions": rounded_scores(entry.get("score_dimensions")),
        "score_focus": [str(value) for value in entry.get("score_focus", []) or []],
        "reliability_score": int(entry.get("reliability_score", 0) or 0),
        "reliability_label": str(entry.get("reliability_label", "") or ""),
        "signal": str(entry.get("signal", "") or ""),
    }


def repo_healthcare_anchor_gate(entry: Dict[str, Any]) -> Dict[str, Any]:
    if str(entry.get("category", "") or "") != "Repo":
        return {
            "affected": False,
            "status": "not_repo",
        }

    is_generic = bool(entry.get("is_generic_devtool"))
    exempt = bool(entry.get("generic_repo_cap_exempt"))
    explicit_healthcare = bool(entry.get("explicit_healthcare_context"))

    if not is_generic:
        status = "not_generic_devtool"
        affected = False
    elif exempt:
        status = "generic_repo_exempted_by_healthcare_or_workflow_anchor"
        affected = True
    else:
        status = "generic_repo_not_exempted"
        affected = True

    return {
        "affected": affected,
        "status": status,
        "is_generic_devtool": is_generic,
        "generic_repo_cap_exempt": exempt,
        "explicit_healthcare_context": explicit_healthcare,
    }


def story_primary_reason(story: Dict[str, Any], *, selected: bool) -> str:
    if selected:
        return "Selected for operator story cards."
    if not story_has_target_fit(story):
        return "Filtered because target-fit check failed."
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return "Filtered because reliability is low without corroborating support."
    if not story_is_surface_worthy(story):
        return "Filtered because story score/objective thresholds were not strong enough."
    return "Filtered by story-card cap or ordering after higher-ranked eligible stories filled the digest."


def daily_story_decisions(operator_brief: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    story_cards = operator_brief.get("story_cards")
    source_stories = story_cards if isinstance(story_cards, list) else operator_brief.get("stories", [])
    candidates = [story for story in (source_stories or []) if isinstance(story, dict)]
    selected_daily = select_daily_stories(operator_brief, story_limit=DAILY_STORY_LIMIT)
    selected_daily_ids = {story_id_for_render(story) for story in selected_daily}

    decisions: Dict[str, Dict[str, Any]] = {}
    selected_so_far: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for story in candidates:
        story_id = story_id_for_render(story)
        duplicate_id = bool(story_id and story_id in seen)
        render_duplicate = stories_are_render_duplicates(story, selected_so_far)

        if duplicate_id:
            status = "filtered"
            reason = "Filtered from daily digest because the story id was already selected."
            duplicate_affected = True
        elif render_duplicate:
            status = "filtered"
            reason = "Filtered from daily digest by render duplicate suppression."
            duplicate_affected = True
        elif len(selected_so_far) >= DAILY_STORY_LIMIT:
            status = "filtered"
            reason = "Filtered from daily digest because the shorter daily story limit was already filled."
            duplicate_affected = False
        else:
            status = "selected"
            reason = "Selected for shorter daily digest from story_cards."
            duplicate_affected = False
            if story_id:
                seen.add(story_id)
            selected_so_far.append(story)

        decisions[story_id] = {
            "status": status,
            "selected": story_id in selected_daily_ids,
            "reason": reason,
            "duplicate_suppression_affected": duplicate_affected,
            "shorter_digest_selection_affected": status == "filtered" and "daily" in reason,
            "backfill_affected": False,
            "backfill_note": "Daily rendering reads story_cards when present; stories outside story_cards are not backfilled.",
        }

    return decisions


def build_story_audit(operator_brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    story_cards = operator_brief.get("story_cards", []) or []
    selected_story_ids = {str(story.get("story_id", "") or "") for story in story_cards if isinstance(story, dict)}
    daily_decisions = daily_story_decisions(operator_brief)

    rows: List[Dict[str, Any]] = []
    for story in operator_brief.get("stories", []) or []:
        if not isinstance(story, dict):
            continue
        story_id = str(story.get("story_id", "") or "")
        selected = story_id in selected_story_ids
        target_fit = story_has_target_fit(story)
        daily = daily_decisions.get(story_id, {
            "status": "not_considered",
            "selected": False,
            "reason": "Not considered for daily digest because it was not selected as a story_card.",
            "duplicate_suppression_affected": False,
            "shorter_digest_selection_affected": True,
            "backfill_affected": True,
            "backfill_note": "Daily rendering reads story_cards when present; this story was not backfilled.",
        })

        rows.append(
            {
                "story_id": story_id,
                "title": str(story.get("cluster_title") or story.get("title") or ""),
                "source_type": str(story.get("item_type") or story.get("category") or ""),
                "sources": [str(value) for value in story.get("source_names", []) or []],
                "status": "selected" if selected else "filtered",
                "selected": selected,
                "primary_reason": story_primary_reason(story, selected=selected),
                "target_fit": {
                    "passes": target_fit,
                    "operator_relevance": str(story.get("operator_relevance", "") or ""),
                    "near_term_actionability": str(story.get("near_term_actionability", "") or ""),
                    "workflow_wedges": [str(value) for value in story.get("workflow_wedges", []) or []],
                    "matched_themes": [str(value) for value in story.get("matched_themes", []) or []],
                },
                "score_summary": score_summary(story),
                "repo_healthcare_anchor_gate": repo_healthcare_anchor_gate(story),
                "duplicate_suppression": {
                    "affected": int(story.get("supporting_item_count", 0) or 0) > 1
                    or bool(daily.get("duplicate_suppression_affected")),
                    "supporting_item_count": int(story.get("supporting_item_count", 0) or 0),
                    "daily_render_duplicate": bool(daily.get("duplicate_suppression_affected")),
                },
                "shorter_digest_selection": daily,
            }
        )
    return rows


def item_primary_reason(item: Dict[str, Any], story_by_id: Dict[str, Dict[str, Any]]) -> str:
    story_id = str(item.get("story_id", "") or "")
    story = story_by_id.get(story_id)
    if not story:
        return "Filtered before story clustering or missing parent story metadata."
    if story.get("selected"):
        return "Selected because its parent story surfaced."
    return f"Filtered because parent story was filtered: {story.get('primary_reason', '')}"


def build_item_audit(
    operator_brief: Dict[str, Any],
    story_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    story_by_id = {row["story_id"]: row for row in story_rows}
    rows: List[Dict[str, Any]] = []
    for item in operator_brief.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        story_id = str(item.get("story_id", "") or "")
        story = story_by_id.get(story_id, {})
        selected = bool(story.get("selected"))
        parent_duplicate = bool((story.get("duplicate_suppression", {}) or {}).get("affected"))
        rows.append(
            {
                "item_id": str(item.get("item_id", "") or ""),
                "story_id": story_id,
                "title": str(item.get("title", "") or ""),
                "source_type": str(item.get("item_type") or item.get("category") or ""),
                "source": str(item.get("source_name") or item.get("source") or ""),
                "status": "selected" if selected else "filtered",
                "selected": selected,
                "primary_reason": item_primary_reason(item, story_by_id),
                "target_fit": {
                    "passes": bool((story.get("target_fit", {}) or {}).get("passes", False)),
                    "operator_relevance": str(item.get("operator_relevance", "") or ""),
                    "near_term_actionability": str(item.get("near_term_actionability", "") or ""),
                    "workflow_wedges": [str(value) for value in item.get("workflow_wedges", []) or []],
                    "matched_themes": [str(value) for value in item.get("matched_themes", []) or []],
                },
                "score_summary": score_summary(item),
                "repo_healthcare_anchor_gate": repo_healthcare_anchor_gate(item),
                "duplicate_suppression": {
                    "affected": parent_duplicate,
                    "duplicate_group_id": str(item.get("duplicate_group_id", "") or ""),
                    "parent_story_supporting_item_count": int(
                        (story.get("duplicate_suppression", {}) or {}).get("supporting_item_count", 0) or 0
                    ),
                },
                "shorter_digest_selection": story.get("shorter_digest_selection", {}),
            }
        )
    return rows


def build_selection_audit(operator_brief: Dict[str, Any]) -> Dict[str, Any]:
    story_rows = build_story_audit(operator_brief)
    item_rows = build_item_audit(operator_brief, story_rows)
    return {
        "version": 1,
        "generated_at": local_now().isoformat(),
        "summary": {
            "raw_item_count": ((operator_brief.get("summary") or {}).get("raw_item_count", 0)),
            "story_count": len(story_rows),
            "story_card_count": len([row for row in story_rows if row["selected"]]),
            "daily_story_limit": DAILY_STORY_LIMIT,
            "daily_selected_story_count": len(
                [
                    row
                    for row in story_rows
                    if (row.get("shorter_digest_selection", {}) or {}).get("selected")
                ]
            ),
        },
        "stories": story_rows,
        "items": item_rows,
    }


def write_selection_audit(
    operator_brief: Dict[str, Any],
    *,
    path: str = SELECTION_AUDIT_FILE_PATH,
) -> Dict[str, Any]:
    audit = build_selection_audit(operator_brief)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    return audit
