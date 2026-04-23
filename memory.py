from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import (
    AppConfig,
    BRIEF_HISTORY_MAX_DAYS,
    HISTORY_CONTEXT_WINDOW_DAYS,
    HISTORY_MAX_EVENTS,
    HISTORY_REPEAT_WINDOW_DAYS,
    current_config,
)
from storage import read_json_file, write_json_file
from taxonomy import theme_label


DigestMemory = Dict[str, Any]


def _resolved_config(config: AppConfig | None = None) -> AppConfig:
    return config or current_config()


def memory_path(*, config: AppConfig | None = None) -> Path:
    return Path(_resolved_config(config).digest_memory_file_path)


def _default_memory() -> DigestMemory:
    return {
        "version": 2,
        "events": [],
        "daily_briefs": [],
    }


def _today_key(*, config: AppConfig | None = None) -> str:
    return datetime.now(ZoneInfo(_resolved_config(config).local_timezone)).date().isoformat()


def _parse_event_date(value: str) -> datetime | None:
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    for candidate in (raw_value, f"{raw_value}T00:00:00+00:00"):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=ZoneInfo("UTC"))
            return parsed
        except ValueError:
            continue
    return None


def load_digest_memory(*, config: AppConfig | None = None) -> DigestMemory:
    data = read_json_file(memory_path(config=config), _default_memory(), expected_type=dict)

    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    cleaned_events: List[Dict[str, Any]] = []
    for event in events[-HISTORY_MAX_EVENTS:]:
        if not isinstance(event, dict):
            continue
        cleaned_events.append(
            {
                "date": str(event.get("date", "") or ""),
                "item_key": str(event.get("item_key", "") or ""),
                "category": str(event.get("category", "") or ""),
                "title": str(event.get("title", "") or ""),
                "url": str(event.get("url", "") or ""),
                "source": str(event.get("source", "") or ""),
                "topic_key": str(event.get("topic_key", "") or ""),
                "themes": [
                    str(theme).strip()
                    for theme in event.get("themes", [])
                    if str(theme).strip()
                ],
                "entities": [
                    str(entity).strip()
                    for entity in event.get("entities", [])
                    if str(entity).strip()
                ],
                "priority_score": float(event.get("priority_score", 0.0) or 0.0),
                "objective_scores": {
                    str(key): float(value or 0.0)
                    for key, value in (event.get("objective_scores", {}) or {}).items()
                    if str(key).strip()
                },
                "signal": str(event.get("signal", "") or ""),
            }
        )

    daily_briefs = data.get("daily_briefs", [])
    if not isinstance(daily_briefs, list):
        daily_briefs = []

    cleaned_briefs: List[Dict[str, Any]] = []
    for brief in daily_briefs[-BRIEF_HISTORY_MAX_DAYS:]:
        if not isinstance(brief, dict):
            continue
        stories = []
        for story in brief.get("stories", []):
            if not isinstance(story, dict):
                continue
            stories.append(
                {
                    "story_id": str(story.get("story_id", "") or ""),
                    "cluster_title": str(story.get("cluster_title", "") or ""),
                    "change_status": str(story.get("change_status", "") or ""),
                    "supporting_item_count": int(story.get("supporting_item_count", 0) or 0),
                    "source_domains": [
                        str(value).strip()
                        for value in story.get("source_domains", [])
                        if str(value).strip()
                    ],
                    "market_bucket_ids": [
                        str(value).strip()
                        for value in story.get("market_bucket_ids", [])
                        if str(value).strip()
                    ],
                    "reliability_label": str(story.get("reliability_label", "") or ""),
                    "story_score": float(story.get("story_score", 0.0) or 0.0),
                    "signature_tokens": [
                        str(value).strip()
                        for value in story.get("signature_tokens", [])
                        if str(value).strip()
                    ],
                    "thesis_links": [
                        {
                            "thesis_id": str(link.get("thesis_id", "") or ""),
                            "relation": str(link.get("relation", "") or ""),
                        }
                        for link in story.get("thesis_links", [])
                        if isinstance(link, dict)
                    ],
                }
            )

        cleaned_briefs.append(
            {
                "date": str(brief.get("date", "") or ""),
                "generated_at": str(brief.get("generated_at", "") or ""),
                "top_insight": str(brief.get("top_insight", "") or ""),
                "stories": stories,
                "quality_eval": brief.get("quality_eval", {}) if isinstance(brief.get("quality_eval", {}), dict) else {},
                "market_map": brief.get("market_map", {}) if isinstance(brief.get("market_map", {}), dict) else {},
                "thesis_tracker": [
                    entry
                    for entry in brief.get("thesis_tracker", [])
                    if isinstance(entry, dict)
                ],
                "watchlist_hits": [
                    entry
                    for entry in brief.get("watchlist_hits", [])
                    if isinstance(entry, dict)
                ],
                "top_picks": brief.get("top_picks", {}) if isinstance(brief.get("top_picks", {}), dict) else {},
            }
        )

    return {
        "version": max(int(data.get("version", 1) or 1), 2),
        "events": cleaned_events,
        "daily_briefs": cleaned_briefs,
    }


def save_digest_memory(memory: DigestMemory, *, config: AppConfig | None = None) -> None:
    write_json_file(memory_path(config=config), memory)


def build_history_context(
    item: Dict[str, Any],
    memory: DigestMemory,
    *,
    themes: List[str],
    entities: List[str],
    now: datetime,
) -> Dict[str, Any]:
    repeat_cutoff = now - timedelta(days=HISTORY_REPEAT_WINDOW_DAYS)
    item_key = str(item.get("item_key", "") or "")

    item_seen_count = 0
    last_seen_at: datetime | None = None
    recent_theme_counts: Counter[str] = Counter()
    recent_entity_counts: Counter[str] = Counter()

    for event in memory.get("events", []):
        event_dt = _parse_event_date(str(event.get("date", "")))
        if not event_dt:
            continue

        if str(event.get("item_key", "")) == item_key:
            item_seen_count += 1
            if last_seen_at is None or event_dt > last_seen_at:
                last_seen_at = event_dt

        if event_dt < repeat_cutoff:
            continue

        for theme in themes:
            if theme in set(event.get("themes", [])):
                recent_theme_counts[theme] += 1
        for entity in entities:
            if entity in set(event.get("entities", [])):
                recent_entity_counts[entity] += 1

    days_since_last_seen: int | None = None
    if last_seen_at is not None:
        days_since_last_seen = max((now - last_seen_at).days, 0)

    return {
        "item_seen_count": item_seen_count,
        "days_since_last_seen": days_since_last_seen,
        "recent_theme_counts": dict(recent_theme_counts),
        "recent_entity_counts": dict(recent_entity_counts),
        "recent_theme_hits": sum(recent_theme_counts.values()),
        "recent_entity_hits": sum(recent_entity_counts.values()),
    }


def build_memory_snapshot(
    memory: DigestMemory,
    *,
    now: datetime | None = None,
) -> Dict[str, Any]:
    now = now or datetime.now(ZoneInfo("UTC"))
    cutoff = now - timedelta(days=HISTORY_CONTEXT_WINDOW_DAYS)
    theme_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()

    for event in memory.get("events", []):
        event_dt = _parse_event_date(str(event.get("date", "")))
        if not event_dt or event_dt < cutoff:
            continue
        theme_counts.update(event.get("themes", []))
        entity_counts.update(event.get("entities", []))

    top_themes = [
        {
            "theme": theme,
            "label": theme_label(theme),
            "count": count,
        }
        for theme, count in theme_counts.most_common(5)
    ]
    top_entities = [
        {"entity": entity, "count": count}
        for entity, count in entity_counts.most_common(5)
    ]
    recent_briefs = []
    market_counts: Counter[str] = Counter()
    thesis_counts: Counter[str] = Counter()
    quality_history: List[Dict[str, Any]] = []

    for brief in memory.get("daily_briefs", [])[-7:]:
        if not isinstance(brief, dict):
            continue
        brief_date = str(brief.get("date", "") or "")
        story_titles = [
            str(story.get("cluster_title", "") or "")
            for story in brief.get("stories", [])
            if isinstance(story, dict) and str(story.get("cluster_title", "") or "").strip()
        ][:3]
        recent_briefs.append(
            {
                "date": brief_date,
                "top_insight": str(brief.get("top_insight", "") or ""),
                "story_titles": story_titles,
            }
        )
        for story in brief.get("stories", []):
            if not isinstance(story, dict):
                continue
            for bucket_id in story.get("market_bucket_ids", []):
                if str(bucket_id).strip():
                    market_counts[str(bucket_id).strip()] += 1
            for link in story.get("thesis_links", []):
                if not isinstance(link, dict):
                    continue
                thesis_id = str(link.get("thesis_id", "") or "").strip()
                relation = str(link.get("relation", "") or "").strip()
                if thesis_id and relation and relation != "adjacent":
                    thesis_counts[thesis_id] += 1

        metrics = (brief.get("quality_eval", {}) or {}).get("metrics", {})
        if isinstance(metrics, dict):
            quality_history.append(
                {
                    "date": brief_date,
                    "signal_to_noise": float(metrics.get("signal_to_noise", 0.0) or 0.0),
                    "novelty": float(metrics.get("novelty", 0.0) or 0.0),
                }
            )

    return {
        "lookback_days": HISTORY_CONTEXT_WINDOW_DAYS,
        "top_themes": top_themes,
        "top_entities": top_entities,
        "event_count": len(memory.get("events", [])),
        "recent_briefs": recent_briefs,
        "top_market_buckets": [
            {"bucket_id": bucket_id, "count": count}
            for bucket_id, count in market_counts.most_common(5)
        ],
        "top_theses": [
            {"thesis_id": thesis_id, "count": count}
            for thesis_id, count in thesis_counts.most_common(5)
        ],
        "quality_history": quality_history[-5:],
    }


def record_digest_items(
    items: List[Dict[str, Any]],
    *,
    config: AppConfig | None = None,
) -> None:
    memory = load_digest_memory(config=config)
    events = list(memory.get("events", []))
    digest_date = _today_key(config=config)

    for item in items:
        events.append(
            {
                "date": digest_date,
                "item_key": str(item.get("item_key", "") or ""),
                "category": str(item.get("category", "") or ""),
                "title": str(item.get("title", "") or ""),
                "url": str(item.get("url", "") or ""),
                "source": str(item.get("source", "") or ""),
                "topic_key": str(item.get("topic_key", "") or ""),
                "themes": [
                    str(theme).strip()
                    for theme in item.get("matched_themes", [])
                    if str(theme).strip()
                ],
                "entities": [
                    str(entity).strip()
                    for entity in item.get("entity_keys", [])
                    if str(entity).strip()
                ],
                "priority_score": round(float(item.get("priority_score", 0.0) or 0.0), 2),
                "story_id": str(item.get("story_id", "") or ""),
                "cluster_id": str(item.get("cluster_id", "") or ""),
                "change_status": str(item.get("change_status", "") or ""),
                "market_buckets": [
                    str(bucket).strip()
                    for bucket in item.get("market_buckets", [])
                    if str(bucket).strip()
                ],
                "thesis_ids": [
                    str(link.get("thesis_id", "")).strip()
                    for link in item.get("thesis_links", [])
                    if isinstance(link, dict) and str(link.get("thesis_id", "")).strip()
                ],
                "objective_scores": {
                    str(key): round(float(value or 0.0), 2)
                    for key, value in (item.get("objective_scores", {}) or {}).items()
                },
                "signal": str(item.get("signal", "") or ""),
            }
        )

    memory["events"] = events[-HISTORY_MAX_EVENTS:]
    save_digest_memory(memory, config=config)


def latest_previous_brief(
    memory: DigestMemory,
    *,
    before_date: str | None = None,
    config: AppConfig | None = None,
) -> Dict[str, Any] | None:
    target_date = before_date or _today_key(config=config)
    candidates = [
        brief
        for brief in memory.get("daily_briefs", [])
        if isinstance(brief, dict) and str(brief.get("date", "") or "").strip() and str(brief.get("date", "") or "") < target_date
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda brief: str(brief.get("date", "") or ""))[-1]


def _brief_history_entry(
    brief: Dict[str, Any],
    *,
    config: AppConfig | None = None,
) -> Dict[str, Any]:
    stories = []
    for story in brief.get("stories", []):
        if not isinstance(story, dict):
            continue
        stories.append(
            {
                "story_id": str(story.get("story_id", "") or ""),
                "cluster_title": str(story.get("cluster_title", "") or ""),
                "change_status": str(story.get("change_status", "") or ""),
                "supporting_item_count": int(story.get("supporting_item_count", 0) or 0),
                "source_domains": [
                    str(value).strip()
                    for value in story.get("source_domains", [])
                    if str(value).strip()
                ],
                "market_bucket_ids": [
                    str(value).strip()
                    for value in story.get("market_bucket_ids", [])
                    if str(value).strip()
                ],
                "reliability_label": str(story.get("reliability_label", "") or ""),
                "story_score": round(float(story.get("story_score", 0.0) or 0.0), 2),
                "signature_tokens": [
                    str(value).strip()
                    for value in story.get("signature_tokens", [])
                    if str(value).strip()
                ],
                "thesis_links": [
                    {
                        "thesis_id": str(link.get("thesis_id", "") or ""),
                        "relation": str(link.get("relation", "") or ""),
                    }
                    for link in story.get("thesis_links", [])
                    if isinstance(link, dict)
                ],
            }
        )

    return {
        "date": str(brief.get("date", "") or _today_key(config=config)),
        "generated_at": str(brief.get("generated_at", "") or ""),
        "top_insight": str(((brief.get("operator_moves", {}) or {}).get("top_insight", "")) or ""),
        "stories": stories,
        "quality_eval": brief.get("quality_eval", {}) if isinstance(brief.get("quality_eval", {}), dict) else {},
        "market_map": brief.get("market_map", {}) if isinstance(brief.get("market_map", {}), dict) else {},
        "thesis_tracker": [
            entry
            for entry in brief.get("thesis_tracker", [])
            if isinstance(entry, dict)
        ],
        "watchlist_hits": [
            entry
            for entry in brief.get("watchlist_hits", [])
            if isinstance(entry, dict)
        ],
        "top_picks": brief.get("top_picks", {}) if isinstance(brief.get("top_picks", {}), dict) else {},
    }


def record_operator_brief(
    brief: Dict[str, Any],
    *,
    config: AppConfig | None = None,
) -> None:
    memory = load_digest_memory(config=config)
    daily_briefs = [
        entry
        for entry in memory.get("daily_briefs", [])
        if isinstance(entry, dict)
    ]
    entry = _brief_history_entry(brief, config=config)
    daily_briefs = [
        brief_entry
        for brief_entry in daily_briefs
        if str(brief_entry.get("date", "") or "") != entry["date"]
    ]
    daily_briefs.append(entry)
    daily_briefs = sorted(
        daily_briefs,
        key=lambda brief_entry: str(brief_entry.get("date", "") or ""),
    )[-BRIEF_HISTORY_MAX_DAYS:]
    memory["version"] = 2
    memory["daily_briefs"] = daily_briefs
    save_digest_memory(memory, config=config)
