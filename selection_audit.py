from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List

from formatter import (
    DAILY_STORY_LIMIT,
    daily_story_passes_render_quality,
    single_daily_story_is_worthy,
    select_daily_stories,
    stories_are_render_duplicates,
    story_id_for_render,
)
from operator_brief import (
    max_story_objective_score,
    story_has_target_fit,
    story_is_surface_worthy,
    story_surface_worthiness,
    story_surface_worthiness_reason,
)
from state import local_now


SELECTION_AUDIT_FILE_PATH = "latest_selection_audit.json"
SELECTION_AUDIT_MARKDOWN_FILE_PATH = "latest_selection_audit.md"


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


def story_lookup_by_id(operator_brief: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(story.get("story_id", "") or ""): story
        for story in operator_brief.get("stories", []) or []
        if isinstance(story, dict) and str(story.get("story_id", "") or "").strip()
    }


def selection_penalties(entry: Dict[str, Any]) -> List[str]:
    penalties = [
        str(value)
        for value in entry.get("selection_penalties", []) or []
        if str(value).strip()
    ]
    if entry.get("low_signal_announcement"):
        penalties.extend(
            [
                "soft_announcement_demoted",
                "confidence_capped_by_materiality",
            ]
        )
    if str(entry.get("signal_quality", "") or "").lower() == "weak":
        penalties.append("weak_signal_quality_confidence_cap")
    if entry.get("is_generic_devtool") and not entry.get("generic_repo_cap_exempt"):
        penalties.append("generic_devtool_score_penalty")
    if entry.get("docs_only_repo"):
        penalties.append("docs_only_repo_score_penalty")

    seen = set()
    result: List[str] = []
    for penalty in penalties:
        if penalty in seen:
            continue
        seen.add(penalty)
        result.append(penalty)
    return result


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


def story_primary_reason(
    story: Dict[str, Any],
    *,
    selected: bool,
    daily_selected: bool = False,
) -> str:
    if selected:
        return "Selected for operator story cards."
    if daily_selected:
        return "Selected as controlled daily backfill from broader stories."
    surface_passes, surface_reason = story_surface_worthiness(story)
    if not surface_passes and (
        "soft announcement" in surface_reason
        or "signal quality" in surface_reason
    ):
        return f"Filtered because {surface_reason}"
    if not story_has_target_fit(story):
        return "Filtered because target-fit check failed."
    if story.get("reliability_label") == "Low" and int(story.get("supporting_item_count", 0) or 0) < 2:
        return "Filtered because reliability is low without corroborating support."
    if not surface_passes:
        return f"Filtered because {story_surface_worthiness_reason(story)}"
    return "Filtered by story-card cap or ordering after higher-ranked eligible stories filled the digest."


def daily_story_decisions(operator_brief: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    story_cards = operator_brief.get("story_cards")
    source_stories = story_cards if isinstance(story_cards, list) else operator_brief.get("stories", [])
    candidates = [story for story in (source_stories or []) if isinstance(story, dict)]
    all_stories = [story for story in (operator_brief.get("stories", []) or []) if isinstance(story, dict)]
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
        elif not daily_story_passes_render_quality(story):
            status = "filtered"
            reason = "Filtered from daily digest by the final daily signal-quality gate."
            duplicate_affected = False
        else:
            status = "selected"
            reason = "Selected for shorter daily digest from story_cards."
            duplicate_affected = False
            if story_id:
                seen.add(story_id)
            selected_so_far.append(story)

        if status == "selected" and story_id not in selected_daily_ids:
            status = "filtered"
            reason = (
                "Filtered from daily digest by the stricter single-story quality gate."
                if len(selected_so_far) == 1 and not single_daily_story_is_worthy(story)
                else "Filtered from daily digest by the final daily quality gate."
            )

        decisions[story_id] = {
            "status": status,
            "selected": story_id in selected_daily_ids,
            "reason": reason,
            "duplicate_suppression_affected": duplicate_affected,
            "shorter_digest_selection_affected": status == "filtered" and "daily" in reason,
            "backfill_affected": False,
            "backfill_selected": False,
            "backfill_note": "Daily rendering reads story_cards when present; stories outside story_cards are not backfilled.",
        }

    for story in all_stories:
        story_id = story_id_for_render(story)
        if not story_id or story_id in decisions:
            continue

        selected = story_id in selected_daily_ids
        decisions[story_id] = {
            "status": "selected" if selected else "not_considered",
            "selected": selected,
            "reason": (
                "Selected as controlled daily backfill from broader stories."
                if selected
                else "Not selected for daily backfill because the daily minimum was already met or the story failed the backfill quality gate."
            ),
            "duplicate_suppression_affected": False,
            "shorter_digest_selection_affected": False,
            "backfill_affected": not selected,
            "backfill_selected": selected,
            "backfill_note": (
                "Daily rendering backfilled this story from broader stories."
                if selected
                else "Daily rendering considered broader stories only when story_cards were below the daily minimum."
            ),
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
        story_card_selected = story_id in selected_story_ids
        target_fit = story_has_target_fit(story)
        daily = daily_decisions.get(story_id, {
            "status": "not_considered",
            "selected": False,
            "reason": "Not considered for daily digest because it was not selected as a story_card.",
            "duplicate_suppression_affected": False,
            "shorter_digest_selection_affected": True,
            "backfill_affected": True,
            "backfill_selected": False,
            "backfill_note": "Daily rendering reads story_cards when present; this story was not backfilled.",
        })
        daily_selected = bool(daily.get("selected"))
        selected = story_card_selected or daily_selected

        rows.append(
            {
                "story_id": story_id,
                "title": str(story.get("cluster_title") or story.get("title") or ""),
                "source_type": str(story.get("item_type") or story.get("category") or ""),
                "sources": [str(value) for value in story.get("source_names", []) or []],
                "status": "selected" if selected else "filtered",
                "selected": selected,
                "story_card_selected": story_card_selected,
                "primary_reason": story_primary_reason(
                    story,
                    selected=story_card_selected,
                    daily_selected=daily_selected,
                ),
                "target_fit": {
                    "passes": target_fit,
                    "operator_relevance": str(story.get("operator_relevance", "") or ""),
                    "near_term_actionability": str(story.get("near_term_actionability", "") or ""),
                    "workflow_wedges": [str(value) for value in story.get("workflow_wedges", []) or []],
                    "matched_themes": [str(value) for value in story.get("matched_themes", []) or []],
                },
                "score_summary": score_summary(story),
                "materiality": {
                    "signal_quality": str(story.get("signal_quality", "") or ""),
                    "materiality_tier": str(story.get("signal_quality", "") or ""),
                    "materiality_reason": str(story.get("materiality_reason", "") or ""),
                    "material_operator_signal": bool(story.get("material_operator_signal")),
                    "low_signal_announcement": bool(story.get("low_signal_announcement")),
                    "soft_funding_or_challenge": bool(story.get("soft_funding_or_challenge")),
                    "materiality_signals": [
                        str(value) for value in story.get("materiality_signals", []) or []
                    ],
                },
                "confidence": str(story.get("confidence", "") or story.get("reliability_label", "") or ""),
                "penalties_demotions": selection_penalties(story),
                "surface_worthiness": {
                    "passes": story_is_surface_worthy(story),
                    "reason": story_surface_worthiness_reason(story),
                },
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
                "materiality": {
                    "signal_quality": str(item.get("signal_quality", "") or ""),
                    "materiality_tier": str(item.get("signal_quality", "") or ""),
                    "materiality_reason": str(item.get("materiality_reason", "") or ""),
                    "material_operator_signal": bool(item.get("material_operator_signal")),
                    "low_signal_announcement": bool(item.get("low_signal_announcement")),
                    "soft_funding_or_challenge": bool(item.get("soft_funding_or_challenge")),
                    "materiality_signals": [
                        str(value) for value in item.get("materiality_signals", []) or []
                    ],
                },
                "confidence": str(item.get("confidence", "") or item.get("reliability_label", "") or ""),
                "penalties_demotions": selection_penalties(item),
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
            "story_card_count": len([row for row in story_rows if row.get("story_card_selected")]),
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


def reason_counts(rows: List[Dict[str, Any]], *, key: str) -> Dict[str, int]:
    counts = Counter(str(row.get(key, "") or "unknown") for row in rows)
    return dict(counts.most_common())


def daily_reason_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(
        str((row.get("shorter_digest_selection", {}) or {}).get("reason", "") or "unknown")
        for row in rows
    )
    return dict(counts.most_common())


def no_signal_fallback_diagnostic(audit: Dict[str, Any]) -> Dict[str, Any]:
    stories = [row for row in audit.get("stories", []) or [] if isinstance(row, dict)]
    daily_selected = [
        row
        for row in stories
        if (row.get("shorter_digest_selection", {}) or {}).get("selected")
    ]
    if daily_selected:
        return {
            "triggered": False,
            "reason": "",
            "screened_item_count": int((audit.get("summary", {}) or {}).get("raw_item_count", 0) or 0),
            "story_count": len(stories),
            "story_card_count": int((audit.get("summary", {}) or {}).get("story_card_count", 0) or 0),
        }

    screened_item_count = int((audit.get("summary", {}) or {}).get("raw_item_count", 0) or 0)
    story_card_count = int((audit.get("summary", {}) or {}).get("story_card_count", 0) or 0)
    filtered = [row for row in stories if not row.get("selected")]
    daily_filtered = [
        row
        for row in stories
        if (row.get("shorter_digest_selection", {}) or {}).get("status") == "filtered"
    ]

    if not stories:
        reason = "no stories were built from screened items"
    elif story_card_count == 0:
        top_reasons = reason_counts(filtered, key="primary_reason")
        top_reason = next(iter(top_reasons), "no story cards passed admission gates")
        reason = f"no story cards passed admission gates: {compact_reason(top_reason)}"
    elif daily_filtered:
        top_daily_reasons = daily_reason_counts(daily_filtered)
        top_reason = next(iter(top_daily_reasons), "daily quality gate filtered all selected story cards")
        reason = f"daily render selected no stories: {compact_reason(top_reason)}"
    else:
        reason = "daily render selected no stories after quality and duplicate gates"

    return {
        "triggered": True,
        "reason": reason,
        "screened_item_count": screened_item_count,
        "story_count": len(stories),
        "story_card_count": story_card_count,
        "filtered_reason_counts": reason_counts(filtered, key="primary_reason"),
        "daily_filter_reason_counts": daily_reason_counts(daily_filtered),
    }


def diagnostic_source(row: Dict[str, Any]) -> str:
    sources = row.get("sources", []) or []
    if sources:
        return ", ".join(str(source) for source in sources[:2])
    return str(row.get("source", "") or "")


def story_selection_diagnostic(
    row: Dict[str, Any],
    story: Dict[str, Any],
    *,
    mode: str,
) -> Dict[str, Any]:
    daily = row.get("shorter_digest_selection", {}) or {}
    daily_selected = bool(daily.get("selected"))
    story_card_selected = bool(row.get("story_card_selected"))
    if mode == "daily":
        admission_decision = "daily_selected" if daily_selected else str(daily.get("status", "not_considered"))
        primary_reason = str(daily.get("reason", "") or row.get("primary_reason", ""))
    else:
        admission_decision = "story_card_selected" if story_card_selected else str(row.get("status", "filtered"))
        primary_reason = str(row.get("primary_reason", ""))

    return {
        "story_id": str(row.get("story_id", "") or ""),
        "title": str(row.get("title", "") or ""),
        "source": diagnostic_source(row),
        "signal_quality": str((row.get("materiality", {}) or {}).get("signal_quality", "") or story.get("signal_quality", "")),
        "materiality_tier": str((row.get("materiality", {}) or {}).get("materiality_tier", "") or story.get("signal_quality", "")),
        "materiality_reason": str((row.get("materiality", {}) or {}).get("materiality_reason", "") or story.get("materiality_reason", "")),
        "operator_relevance": str((row.get("target_fit", {}) or {}).get("operator_relevance", "") or story.get("operator_relevance", "")),
        "confidence": str(row.get("confidence", "") or story.get("confidence", "")),
        "admission_decision": admission_decision,
        "primary_reason_selected": primary_reason,
        "penalties_demotions": row.get("penalties_demotions", []) or selection_penalties(story),
    }


def build_selection_diagnostics(
    operator_brief: Dict[str, Any],
    *,
    mode: str = "daily",
) -> Dict[str, Any]:
    normalized_mode = str(mode or "daily").strip().lower()
    audit = build_selection_audit(operator_brief)
    story_lookup = story_lookup_by_id(operator_brief)
    stories = [row for row in audit.get("stories", []) or [] if isinstance(row, dict)]
    if normalized_mode == "daily":
        selected_rows = [
            row
            for row in stories
            if (row.get("shorter_digest_selection", {}) or {}).get("selected")
        ]
    else:
        selected_rows = [row for row in stories if row.get("story_card_selected")]

    return {
        "version": 1,
        "mode": normalized_mode,
        "generated_at": audit["generated_at"],
        "selected_stories": [
            story_selection_diagnostic(
                row,
                story_lookup.get(str(row.get("story_id", "") or ""), {}),
                mode=normalized_mode,
            )
            for row in selected_rows
        ],
        "no_signal_fallback": no_signal_fallback_diagnostic(audit),
    }


def markdown_escape(value: Any) -> str:
    return str(value or "").replace("\n", " ").strip()


def story_score(row: Dict[str, Any]) -> float:
    scores = row.get("score_summary", {}) or {}
    return float(scores.get("story_score", scores.get("priority_score", 0.0)) or 0.0)


def compact_reason(reason: str) -> str:
    return reason.replace("Filtered because ", "").replace("Selected because ", "").strip()


def target_fit_label(row: Dict[str, Any]) -> str:
    target_fit = row.get("target_fit", {}) or {}
    status = "pass" if target_fit.get("passes") else "fail"
    operator_relevance = target_fit.get("operator_relevance", "")
    actionability = target_fit.get("near_term_actionability", "")
    wedges = ", ".join(target_fit.get("workflow_wedges", []) or [])
    suffix = f"; {wedges}" if wedges else ""
    return f"{status}; relevance={operator_relevance}; actionability={actionability}{suffix}"


def daily_label(row: Dict[str, Any]) -> str:
    daily = row.get("shorter_digest_selection", {}) or {}
    status = daily.get("status", "not_considered")
    reason = daily.get("reason", "")
    if status == "selected":
        return "daily selected"
    if not reason:
        return str(status)
    return f"{status}: {compact_reason(str(reason))}"


def source_label(row: Dict[str, Any]) -> str:
    source_type = markdown_escape(row.get("source_type", ""))
    sources = row.get("sources", []) or []
    if sources:
        return f"{source_type} from {', '.join(markdown_escape(source) for source in sources[:2])}"
    source = markdown_escape(row.get("source", ""))
    return f"{source_type} from {source}" if source else source_type


def render_story_line(row: Dict[str, Any]) -> str:
    title = markdown_escape(row.get("title", "Untitled"))
    score = story_score(row)
    return (
        f"- {title} ({source_label(row)}): score {score:.2f}; "
        f"target {target_fit_label(row)}; {daily_label(row)}"
    )


def render_filtered_line(row: Dict[str, Any]) -> str:
    title = markdown_escape(row.get("title", "Untitled"))
    score = story_score(row)
    reason = compact_reason(str(row.get("primary_reason", "")))
    return (
        f"- {title}: score {score:.2f}; target {target_fit_label(row)}; "
        f"reason: {reason}"
    )


def render_duplicate_line(row: Dict[str, Any]) -> str:
    title = markdown_escape(row.get("title", "Untitled"))
    duplicate = row.get("duplicate_suppression", {}) or {}
    support_count = int(duplicate.get("supporting_item_count", 0) or 0)
    daily_duplicate = bool(duplicate.get("daily_render_duplicate"))
    details = []
    if support_count > 1:
        details.append(f"{support_count} supporting items clustered")
    if daily_duplicate:
        details.append("daily render duplicate suppressed")
    detail = "; ".join(details) if details else "duplicate suppression affected this row"
    return f"- {title}: {detail}"


def render_selection_audit_markdown(audit: Dict[str, Any]) -> str:
    stories = [row for row in audit.get("stories", []) or [] if isinstance(row, dict)]
    selected = [row for row in stories if row.get("selected")]
    filtered = [row for row in stories if not row.get("selected")]
    daily_selected = [
        row
        for row in stories
        if (row.get("shorter_digest_selection", {}) or {}).get("selected")
    ]
    daily_filtered = [
        row
        for row in stories
        if (row.get("shorter_digest_selection", {}) or {}).get("status") == "filtered"
    ]
    daily_backfilled = [
        row
        for row in daily_selected
        if (row.get("shorter_digest_selection", {}) or {}).get("backfill_selected")
    ]
    target_fit_filtered = [
        row
        for row in filtered
        if not (row.get("target_fit", {}) or {}).get("passes")
    ]
    duplicate_rows = [
        row
        for row in stories
        if (row.get("duplicate_suppression", {}) or {}).get("affected")
    ]
    backfill_filtered = [
        row
        for row in stories
        if (row.get("shorter_digest_selection", {}) or {}).get("backfill_affected")
    ]
    reason_counts = Counter(str(row.get("primary_reason", "") or "Unknown") for row in filtered)
    daily_limit_count = sum(
        1
        for row in daily_filtered
        if "shorter daily story limit" in str(
            (row.get("shorter_digest_selection", {}) or {}).get("reason", "")
        )
    )
    daily_duplicate_count = sum(
        1
        for row in daily_filtered
        if bool((row.get("shorter_digest_selection", {}) or {}).get("duplicate_suppression_affected"))
    )

    lines = [
        "# Selection Audit Summary",
        "",
        "## Summary",
        f"- Stories: {len(selected)} surfaced, {len(filtered)} filtered.",
        (
            f"- Daily digest: {len(daily_selected)} selected "
            f"({len(daily_backfilled)} backfilled), {len(daily_filtered)} filtered "
            f"after daily selection, limit {audit.get('summary', {}).get('daily_story_limit', 0)}."
        ),
        (
            f"- Short-digest effect: {daily_limit_count} filtered by daily limit, "
            f"{daily_duplicate_count} duplicate-suppressed, {len(backfill_filtered)} not backfilled from broader stories."
        ),
        f"- Target-fit failures among filtered stories: {len(target_fit_filtered)}.",
        "",
        "## Surfaced Stories",
    ]

    if selected:
        lines.extend(render_story_line(row) for row in selected[:6])
    else:
        lines.append("- None.")

    lines.extend(["", "## Top Filtered Near-Misses"])
    near_misses = sorted(filtered, key=story_score, reverse=True)[:5]
    if near_misses:
        lines.extend(render_filtered_line(row) for row in near_misses)
    else:
        lines.append("- None.")

    lines.extend(["", "## Duplicate-Suppressed Items"])
    if duplicate_rows:
        lines.extend(render_duplicate_line(row) for row in duplicate_rows[:5])
    else:
        lines.append("- None.")

    lines.extend(["", "## Most Common Exclusion Reasons"])
    if reason_counts:
        for reason, count in reason_counts.most_common(5):
            lines.append(f"- {count}x {compact_reason(reason)}")
    else:
        lines.append("- None.")

    return "\n".join(lines) + "\n"


def write_selection_audit(
    operator_brief: Dict[str, Any],
    *,
    path: str = SELECTION_AUDIT_FILE_PATH,
    markdown_path: str = SELECTION_AUDIT_MARKDOWN_FILE_PATH,
) -> Dict[str, Any]:
    audit = build_selection_audit(operator_brief)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(render_selection_audit_markdown(audit))
    return audit
