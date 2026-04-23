from __future__ import annotations

from typing import Callable, Dict, List

from selection_policy import (
    DAILY_BACKFILL_MIN_OBJECTIVE_SCORE,
    DAILY_BACKFILL_MIN_STORY_SCORE,
    DAILY_MIN_STORY_COUNT,
    DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE,
    DAILY_SINGLE_STORY_MIN_STORY_SCORE,
    DAILY_STORY_LIMIT,
    NEAR_MISS_LIMIT,
    TARGET_THEME_KEYS,
)
from state import local_now

from formatter_shared import (
    CATEGORY_HEADINGS,
    SECTION_ORDER,
    build_summary_line,
    category_count_label,
    compact_text,
    escaped,
    max_story_objective_score_for_render,
    normalized_words,
    sentence_limited,
    singular_plural,
    sort_items_for_render,
    stories_are_render_duplicates,
    story_float,
    story_has_material_signal_for_render,
    story_id_for_render,
    story_int,
    story_is_low_signal_for_render,
    story_list_values,
    story_objective_score,
    story_signal_quality_for_render,
    story_source_confidence_line,
    story_title_for_render,
    story_url_for_render,
    should_render_daily_action,
    validate_digest_items,
)


def daily_backfill_has_target_fit(story: Dict[str, object]) -> bool:
    category = compact_text(story.get("category"))
    operator_relevance = compact_text(story.get("operator_relevance") or "low").lower()
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    workflow_wedges = story_list_values(story, "workflow_wedges")
    matched_themes = set(story_list_values(story, "matched_themes"))
    max_objective = max_story_objective_score_for_render(story)
    has_watchlist_match = bool(story.get("watchlist_matches"))

    if bool(story.get("docs_only_repo")):
        return False
    if story_is_low_signal_for_render(story) or story_signal_quality_for_render(story) == "weak":
        return False

    if category == "Regulatory":
        regulatory_score = story_objective_score(story, "regulatory")
        return (
            regulatory_score >= 6.1
            or bool(workflow_wedges)
            or operator_relevance in {"high", "medium"}
        )

    if category == "Repo":
        is_generic = bool(story.get("is_generic_devtool"))
        is_exempt = bool(story.get("generic_repo_cap_exempt"))
        if is_generic and not is_exempt:
            return has_watchlist_match or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_objective >= 7.2
                and actionability != "low"
            )
        return (
            has_watchlist_match
            or bool(workflow_wedges)
            or operator_relevance == "high"
            or (
                "llm_eval_rag_governance_safety" in matched_themes
                and max_objective >= DAILY_BACKFILL_MIN_OBJECTIVE_SCORE
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


def daily_backfill_story_is_worthy(story: Dict[str, object]) -> bool:
    if not daily_backfill_has_target_fit(story):
        return False
    if compact_text(story.get("reliability_label")).lower() == "low" and story_int(story, "supporting_item_count") < 2:
        return False

    story_score = story_float(story, "story_score", story_float(story, "priority_score"))
    max_objective = max_story_objective_score_for_render(story)
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    support_count = story_int(story, "supporting_item_count")

    return (
        story_score >= DAILY_BACKFILL_MIN_STORY_SCORE
        or max_objective >= DAILY_BACKFILL_MIN_OBJECTIVE_SCORE
        or (support_count >= 2 and actionability in {"high", "medium"})
    )


def daily_story_passes_render_quality(story: Dict[str, object]) -> bool:
    return not story_is_low_signal_for_render(story) and story_signal_quality_for_render(story) != "weak"


def single_daily_story_is_worthy(story: Dict[str, object]) -> bool:
    if not daily_story_passes_render_quality(story):
        return False

    story_score = story_float(story, "story_score", story_float(story, "priority_score"))
    max_objective = max_story_objective_score_for_render(story)
    actionability = compact_text(story.get("near_term_actionability") or "low").lower()
    support_count = story_int(story, "supporting_item_count", 1)
    has_score_evidence = (
        "story_score" in story
        or "priority_score" in story
        or bool(story.get("objective_scores"))
    )

    if story_has_material_signal_for_render(story):
        if not has_score_evidence:
            return True
        return (
            story_score >= DAILY_SINGLE_STORY_MIN_STORY_SCORE
            or max_objective >= DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE
            or support_count >= 2
        )

    return (
        story_score >= DAILY_SINGLE_STORY_MIN_STORY_SCORE
        and max_objective >= DAILY_SINGLE_STORY_MIN_OBJECTIVE_SCORE
        and actionability == "high"
    )


def daily_backfill_rank(story: Dict[str, object]) -> tuple[float, float, int, int, str]:
    return (
        story_float(story, "story_score", story_float(story, "priority_score")),
        max_story_objective_score_for_render(story),
        story_int(story, "reliability_score"),
        story_int(story, "supporting_item_count"),
        story_title_for_render(story),
    )


def append_daily_story(
    story: Dict[str, object],
    selected: List[Dict[str, object]],
    seen: set[str],
) -> bool:
    story_id = story_id_for_render(story)
    if story_id and story_id in seen:
        return False
    if stories_are_render_duplicates(story, selected):
        return False
    if story_id:
        seen.add(story_id)
    selected.append(story)
    return True


def daily_collapse_reason(code: str, reason: str) -> Dict[str, object]:
    return {
        "triggered": True,
        "code": code,
        "reason": reason,
    }


def no_daily_collapse() -> Dict[str, object]:
    return {
        "triggered": False,
        "code": "",
        "reason": "",
    }


def select_daily_stories_with_diagnostics(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> Dict[str, object]:
    story_limit = max(1, story_limit)
    story_cards = operator_brief.get("story_cards")
    all_stories = [
        story
        for story in (operator_brief.get("stories", []) or [])
        if isinstance(story, dict)
    ]
    primary_candidates = story_cards if isinstance(story_cards, list) else all_stories
    candidates = [
        story
        for story in (primary_candidates or [])
        if isinstance(story, dict)
    ]

    selected: List[Dict[str, object]] = []
    seen: set[str] = set()
    render_quality_filtered = 0
    duplicate_filtered = 0
    for story in candidates:
        if not daily_story_passes_render_quality(story):
            render_quality_filtered += 1
            continue
        if not append_daily_story(story, selected, seen):
            duplicate_filtered += 1
        if len(selected) >= story_limit:
            break

    backfill_target = min(story_limit, DAILY_MIN_STORY_COUNT)
    backfill_candidates: List[Dict[str, object]] = []
    backfill_selected = 0
    if isinstance(story_cards, list) and len(selected) < backfill_target:
        backfill_candidates = [
            story
            for story in all_stories
            if daily_backfill_story_is_worthy(story)
        ]
        for story in sorted(backfill_candidates, key=daily_backfill_rank, reverse=True):
            if append_daily_story(story, selected, seen):
                backfill_selected += 1
            if len(selected) >= backfill_target:
                break

    single_story_rejected = False
    rejected_single_story_id = ""
    if len(selected) == 1 and not single_daily_story_is_worthy(selected[0]):
        single_story_rejected = True
        rejected_single_story_id = story_id_for_render(selected[0])
        selected = []

    if selected:
        collapse_reason = no_daily_collapse()
    elif not all_stories:
        collapse_reason = daily_collapse_reason(
            "no_stories_built",
            "No stories were built from screened items.",
        )
    elif single_story_rejected:
        collapse_reason = daily_collapse_reason(
            "single_story_failed_stricter_gate",
            "Exactly one story survived daily selection but failed the stricter single-story quality gate.",
        )
    elif isinstance(story_cards, list) and not story_cards:
        collapse_reason = daily_collapse_reason(
            "no_story_cards_passed_admission",
            "No story cards passed the main admission gates.",
        )
    elif candidates and render_quality_filtered >= len(candidates):
        collapse_reason = daily_collapse_reason(
            "story_cards_failed_render_quality",
            "Story cards existed, but all failed the final daily render-quality gate.",
        )
    elif isinstance(story_cards, list) and len(selected) < backfill_target and not backfill_candidates:
        collapse_reason = daily_collapse_reason(
            "no_backfill_candidates_passed_daily_gate",
            "Story cards were below the daily minimum and no broader story passed the daily backfill gate.",
        )
    else:
        collapse_reason = daily_collapse_reason(
            "daily_selection_empty_after_quality_duplicate_and_backfill_gates",
            "Daily selection ended empty after quality, duplicate, single-story, and backfill gates.",
        )

    return {
        "stories": selected,
        "collapse_reason": collapse_reason,
        "selection_counts": {
            "story_limit": story_limit,
            "all_story_count": len(all_stories),
            "primary_candidate_count": len(candidates),
            "story_card_count": len(story_cards) if isinstance(story_cards, list) else None,
            "render_quality_filtered_count": render_quality_filtered,
            "duplicate_filtered_count": duplicate_filtered,
            "backfill_candidate_count": len(backfill_candidates),
            "backfill_selected_count": backfill_selected,
            "selected_count": len(selected),
            "single_story_rejected": single_story_rejected,
            "rejected_single_story_id": rejected_single_story_id,
        },
    }


def select_daily_stories(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> List[Dict[str, object]]:
    result = select_daily_stories_with_diagnostics(operator_brief, story_limit=story_limit)
    return [
        story
        for story in result.get("stories", []) or []
        if isinstance(story, dict)
    ]


def build_daily_story_header(
    operator_brief: Dict[str, object],
    stories: List[Dict[str, object]],
) -> str:
    summary = operator_brief.get("summary", {}) or {}
    screened_count = int(summary.get("raw_item_count", 0) or 0)
    if screened_count <= 0:
        screened_count = len(stories)

    counts = {category: 0 for category in SECTION_ORDER}
    for story in stories:
        category = compact_text(story.get("category"))
        if category in counts:
            counts[category] += 1

    category_parts = [
        category_count_label(category, count)
        for category, count in counts.items()
        if count
    ]
    screened_label = singular_plural(screened_count, "screened item")
    if not stories:
        return f"No strong signal today from {screened_label}."
    if len(category_parts) == 1:
        category = next(category for category, count in counts.items() if count)
        category_story_label = {
            "Repo": ("repo story", "repo stories"),
            "News": ("news story", "news stories"),
            "Regulatory": ("regulatory story", "regulatory stories"),
        }[category]
        return (
            f"{singular_plural(len(stories), category_story_label[0], category_story_label[1])} "
            f"selected from {screened_label}."
        )

    category_tail = f" ({', '.join(category_parts)})" if category_parts else ""
    return (
        f"{singular_plural(len(stories), 'story', 'stories')} selected from "
        f"{screened_label}{category_tail}."
    )


def render_daily_headlines(stories: List[Dict[str, object]]) -> str:
    if not stories:
        return """
        <p style="margin: 8px 0 14px 0; color:#555;">No operator-grade stories cleared today's quality bar.</p>
        """
    if len(stories) == 1:
        return ""

    return """
        <p style="margin: 12px 0 8px 0; font-size: 12px; font-weight: 700; color:#555; letter-spacing: 0.02em;">
          HEADLINES
        </p>
    """


def render_daily_near_misses(
    near_miss_items: List[Dict[str, object]] | None,
    *,
    stories: List[Dict[str, object]],
) -> str:
    if stories or not near_miss_items:
        return ""

    rows = []
    for item in near_miss_items[:NEAR_MISS_LIMIT]:
        title = compact_text(item.get("title"))
        summary = sentence_limited(item.get("summary"), 1)
        miss_reason = compact_text(item.get("miss_reason"))
        if not title or not summary or not miss_reason:
            continue
        rows.append(
            f"""
            <li style="margin: 0 0 8px 0;">
              <strong>{escaped(title)}:</strong> {escaped(summary)}
              Did not clear the bar because {escaped(miss_reason)}.
            </li>
            """
        )

    if not rows:
        return ""

    return f"""
        <div style="margin: 4px 0 14px 0; padding-top: 4px;">
          <p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 700; color:#555; letter-spacing: 0.02em;">
            WORTH A QUICK GLANCE
          </p>
          <ul style="margin: 0; padding-left: 18px; color:#333;">
            {''.join(rows)}
          </ul>
        </div>
    """


def render_daily_skipped_news(
    skipped_news_items: List[Dict[str, object]] | None,
    *,
    stories: List[Dict[str, object]],
    near_miss_items: List[Dict[str, object]] | None,
) -> str:
    if stories or near_miss_items or not skipped_news_items:
        return ""

    rows = []
    for item in skipped_news_items:
        title = compact_text(item.get("title"))
        summary = sentence_limited(item.get("summary"), 1)
        skip_reason = compact_text(item.get("skip_reason"))
        if not title or not summary or not skip_reason:
            continue
        rows.append(
            f"""
            <li style="margin: 0 0 8px 0;">
              <strong>{escaped(title)}:</strong> {escaped(summary)}
              Skipped because {escaped(skip_reason)}.
            </li>
            """
        )

    if not rows:
        return ""

    return f"""
        <div style="margin: 4px 0 14px 0; padding-top: 4px;">
          <p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 700; color:#555; letter-spacing: 0.02em;">
            SCREENED BUT SKIPPED
          </p>
          <ul style="margin: 0; padding-left: 18px; color:#333;">
            {''.join(rows)}
          </ul>
        </div>
    """


def render_daily_story_cards(stories: List[Dict[str, object]]) -> str:
    if not stories:
        return ""

    cards = []
    for story in stories:
        summary = sentence_limited(story.get("summary"), 1)
        why_it_matters = sentence_limited(story.get("why_it_matters"), 1)
        action = sentence_limited(story.get("action_suggestion"), 1).rstrip(".!?")
        action_line = ""
        if action and should_render_daily_action(story, action):
            action_line = f"""
              <p style="margin: 0 0 8px 0;"><strong>Action:</strong> {escaped(action)}</p>
            """

        cards.append(
            f"""
            <div style="padding: 14px 0; border-top: 1px solid #e5e7eb;">
              <p style="margin: 0 0 4px 0; font-size: 17px; font-weight: 700; line-height: 1.3;">
                {escaped(story_title_for_render(story))}
              </p>
              <p style="margin: 0 0 8px 0; color:#555; font-size: 13px;">
                {escaped(story_source_confidence_line(story))}
              </p>
              <p style="margin: 0 0 8px 0;"><strong>Summary:</strong> {escaped(summary)}</p>
              <p style="margin: 0 0 8px 0;"><strong>Why it matters:</strong> {escaped(why_it_matters)}</p>
              {action_line}
              <p style="margin: 0;">
                <a href="{escaped(story_url_for_render(story))}" style="color:#0b57d0; text-decoration:none; font-weight:700;">Link</a>
              </p>
            </div>
            """
        )

    return f"""
        <div style="margin: 0;">
          {''.join(cards)}
        </div>
    """


def format_daily_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
    now_fn: Callable[[], object] = local_now,
) -> str:
    date_str = now_fn().strftime("%B %d, %Y")
    daily_selection = select_daily_stories_with_diagnostics(operator_brief, story_limit=story_limit)
    stories = [
        story
        for story in daily_selection.get("stories", []) or []
        if isinstance(story, dict)
    ]
    near_miss_items = operator_brief.get("near_miss_items", []) or []

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.42; color: #222; max-width: 680px; margin: 0 auto; padding: 12px; background: #ffffff;">
        <h2 style="margin: 0 0 4px 0; font-size: 22px; line-height: 1.25;">Daily AI Digest - {date_str}</h2>
        <p style="margin: 0 0 8px 0; color:#444;">{escaped(build_daily_story_header(operator_brief, stories))}</p>
        {render_daily_headlines(stories)}
        {render_daily_near_misses(near_miss_items, stories=stories)}
        {render_daily_skipped_news(
            operator_brief.get("skipped_news_items", []) or [],
            stories=stories,
            near_miss_items=near_miss_items,
        )}
        {render_daily_story_cards(stories)}
      </body>
    </html>
    """
    return html


def format_digest_html(
    items: List[Dict[str, str]],
    top_insight: str,
    top_picks: List[Dict[str, object]] | None = None,
    action_brief: Dict[str, str] | None = None,
    *,
    story_limit: int = DAILY_STORY_LIMIT,
    now_fn: Callable[[], object] = local_now,
) -> str:
    del top_insight, top_picks, action_brief
    counts = validate_digest_items(items)
    sorted_items = sort_items_for_render(items)
    surfaced_items = sorted_items[: max(1, story_limit)]
    stories: List[Dict[str, object]] = []
    for item in surfaced_items:
        confidence = compact_text(item.get("confidence") or item.get("signal", "medium")).title()
        stories.append(
            {
                "cluster_title": item.get("title", "Untitled"),
                "canonical_url": item.get("url", "#"),
                "source_names": [item.get("source") or CATEGORY_HEADINGS.get(item.get("category", ""), "Unknown source")],
                "confidence": confidence,
                "summary": item.get("summary", ""),
                "why_it_matters": item.get("why_it_matters", ""),
                "category": item.get("category", ""),
                "priority_score": item.get("priority_score", 0.0),
            }
        )
    date_str = now_fn().strftime("%B %d, %Y")
    header = f"Showing {singular_plural(len(stories), 'story', 'stories')} from {singular_plural(len(items), 'item')}: {build_summary_line(counts)}"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.42; color: #222; max-width: 680px; margin: 0 auto; padding: 12px;">
        <h2 style="margin: 0 0 4px 0; font-size: 22px; line-height: 1.25;">Daily AI Digest - {date_str}</h2>
        <p style="margin: 0 0 8px 0; color:#444;">{escaped(header)}</p>
        {render_daily_headlines(stories)}
        {render_daily_story_cards(stories)}
      </body>
    </html>
    """
    return html
