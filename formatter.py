from __future__ import annotations

from typing import Dict, List

from selection_policy import DAILY_STORY_LIMIT
from state import local_now as _state_local_now

from formatter_daily import (
    build_daily_story_header,
    daily_backfill_has_target_fit,
    daily_backfill_rank,
    daily_backfill_story_is_worthy,
    daily_collapse_reason,
    daily_story_passes_render_quality,
    format_daily_operator_brief_html as _format_daily_operator_brief_html,
    format_digest_html as _format_digest_html,
    no_daily_collapse,
    render_daily_headlines,
    render_daily_near_misses,
    render_daily_skipped_news,
    render_daily_story_cards,
    select_daily_stories,
    select_daily_stories_with_diagnostics,
    single_daily_story_is_worthy,
)
from formatter_shared import (
    CATEGORY_HEADINGS,
    CHANGE_STYLES,
    RELIABILITY_STYLES,
    SECTION_ORDER,
    SIGNAL_STYLES,
    build_section_counts,
    build_summary_line,
    category_count_label,
    compact_text,
    escaped,
    normalized_words,
    render_category_badge,
    render_change_badge,
    render_inline_badge,
    render_reliability_badge,
    render_signal_badge,
    render_title_tokens,
    sentence_limited,
    should_render_daily_action,
    singular_plural,
    sort_items_for_render,
    stories_are_render_duplicates,
    story_confidence_label,
    story_float,
    story_has_material_signal_for_render,
    story_id_for_render,
    story_int,
    story_is_low_signal_for_render,
    story_list_values,
    story_objective_score,
    story_signal_quality_for_render,
    story_source_confidence_line,
    story_source_names,
    story_title_for_render,
    story_url_for_render,
    validate_digest_items,
)
from formatter_weekly import (
    format_weekly_operator_brief_html as _format_weekly_operator_brief_html,
    render_action_footer,
    render_change_section,
    render_market_map,
    render_quality_flags,
    render_thesis_tracker,
    render_top_picks,
    render_watchlist_hits,
    render_weekly_story_cards,
)


# Compatibility patch point for tests that patch formatter.local_now.
local_now = _state_local_now


def format_daily_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    return _format_daily_operator_brief_html(
        operator_brief,
        story_limit=story_limit,
        now_fn=local_now,
    )


def format_weekly_operator_brief_html(operator_brief: Dict[str, object]) -> str:
    return _format_weekly_operator_brief_html(operator_brief, now_fn=local_now)


def format_operator_brief_html(
    operator_brief: Dict[str, object],
    *,
    mode: str = "daily",
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    normalized_mode = compact_text(mode).lower() or "daily"
    if normalized_mode == "daily":
        return format_daily_operator_brief_html(operator_brief, story_limit=story_limit)
    if normalized_mode == "weekly":
        return format_weekly_operator_brief_html(operator_brief)
    raise ValueError("mode must be 'daily' or 'weekly'.")


def format_operator_cockpit_html(operator_brief: Dict[str, object]) -> str:
    return format_weekly_operator_brief_html(operator_brief)


def format_digest_html(
    items: List[Dict[str, str]],
    top_insight: str,
    top_picks: List[Dict[str, object]] | None = None,
    action_brief: Dict[str, str] | None = None,
    *,
    story_limit: int = DAILY_STORY_LIMIT,
) -> str:
    return _format_digest_html(
        items,
        top_insight,
        top_picks,
        action_brief,
        story_limit=story_limit,
        now_fn=local_now,
    )
