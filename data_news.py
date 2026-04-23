from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import List

import feedparser

from config import AppConfig, current_config
from memory import DigestMemory
from state import get_sent_item_keys

from data_common import DigestItem, item_key, log_section_debug, normalize_text, parse_feed_datetime, select_scored_items, truncate


def fetch_news_items(
    memory: DigestMemory | None = None,
    *,
    config: AppConfig | None = None,
) -> List[DigestItem]:
    resolved = config or current_config()
    results: List[DigestItem] = []
    sent_item_keys = get_sent_item_keys(config=resolved)
    excluded_reasons: Counter[str] = Counter()
    raw_count = 0

    if not resolved.news_feed_urls:
        excluded_reasons["no_feed_urls_configured"] += 1

    for feed_url in resolved.news_feed_urls:
        feed = feedparser.parse(feed_url)
        entries = list(feed.entries[:10])

        if getattr(feed, "bozo", 0) and not entries:
            excluded_reasons["feed_parse_error"] += 1
            continue
        if not entries:
            excluded_reasons["feed_empty"] += 1
            continue

        for entry in entries:
            raw_count += 1
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").strip()
            if not title or not url:
                excluded_reasons["missing_title_or_url"] += 1
                continue

            summary = entry.get("summary", "") or entry.get("description", "")
            results.append(
                {
                    "category": "News",
                    "title": title,
                    "url": url,
                    "raw_text": truncate(f"{title}. {summary}"),
                    "item_key": item_key("News", title, url),
                    "published_at": parse_feed_datetime(entry),
                    "source": feed_url,
                }
            )

    seen_titles = set()
    deduped: List[DigestItem] = []
    for item in sorted(
        results,
        key=lambda entry: entry.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        title_key = normalize_text(item.get("title", ""))
        if title_key and title_key in seen_titles:
            excluded_reasons["duplicate_title"] += 1
            continue
        if title_key:
            seen_titles.add(title_key)
        deduped.append(item)

    selected = select_scored_items(
        deduped,
        sent_item_keys=sent_item_keys,
        limit=resolved.max_items_per_category,
        memory=memory,
    )
    log_section_debug("News", raw_count, len(deduped), excluded_reasons, selected)
    return selected
