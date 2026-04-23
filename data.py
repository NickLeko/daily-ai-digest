from __future__ import annotations

from typing import List

from app_logging import info
from config import AppConfig, REGULATORY_TARGET_ITEMS, current_config
from memory import DigestMemory, load_digest_memory

from data_common import (
    DigestItem,
    empty_source_stats,
    format_excluded_reasons,
    format_score_breakdown,
    format_selected_items,
    iso_days_ago,
    item_key,
    log_regulatory_source_debug,
    log_section_debug,
    normalize_text,
    parse_fda_datetime,
    parse_feed_datetime,
    parse_iso_datetime,
    select_scored_items,
    strip_html,
    title_tokens,
    titles_are_similar,
    truncate,
)
from data_news import fetch_news_items
from data_regulatory import (
    REGULATORY_FEED_SOURCES,
    discover_feed_url,
    fetch_cms_regulatory_items,
    fetch_fda_press_release_items,
    fetch_ocr_regulatory_items,
    fetch_onc_regulatory_items,
    fetch_openfda_regulatory_items,
    fetch_regulatory_items,
    infer_regulatory_subcategory,
    infer_topic_key,
    keyword_matches_text,
    matched_keywords,
    parse_cms_newsroom_html,
    regulatory_entry_matches_keywords,
    regulatory_relevance_result,
)
from data_regulatory_select import (
    REGULATORY_FRESH_WINDOW,
    REGULATORY_MIN_SELECTION_SCORE,
    REGULATORY_RECALL_CAP,
    REGULATORY_RECENT_WINDOW,
    classify_regulatory_skip_reason,
    is_unusually_strong_recall,
    recall_class_level,
    regulatory_base_breakdown,
    regulatory_bucket,
    regulatory_is_fresh,
    regulatory_selection_breakdown,
    select_regulatory_items,
)
from data_repo import REPO_EXCLUDED_KEYWORDS, REPO_RELEVANT_KEYWORDS, fetch_github_repos, repo_is_relevant


def get_real_items(
    memory: DigestMemory | None = None,
    *,
    config: AppConfig | None = None,
) -> List[DigestItem]:
    resolved = config or current_config()
    memory = memory or load_digest_memory(config=resolved)
    repo_items = fetch_github_repos(memory, config=resolved)
    news_items = fetch_news_items(memory, config=resolved)
    regulatory_items = fetch_regulatory_items(memory, config=resolved)

    info(
        "Final section counts",
        repos=len(repo_items),
        news=len(news_items),
        regulatory=len(regulatory_items),
    )

    return repo_items + news_items + regulatory_items
